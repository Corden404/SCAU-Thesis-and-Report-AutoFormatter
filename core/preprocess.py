import os
import re
import sys
import subprocess
import time
import json
import urllib.request
import urllib.error

# 尝试导入剪切板库，如果没有安装则提示
try:
    import pyperclip
except ImportError:
    print("[Error] 缺少 pyperclip 库。请运行: pip install pyperclip")
    sys.exit(1)

# 尝试导入 OpenAI，如果只用网页版模式可以不需要，但为了兼容性保留
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ================= 配置区域 =================
# API 配置现在通过 GUI 传入，不再硬编码

# 路径配置（以项目根目录为基准）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_FILE = os.path.join(BASE_DIR, "prompt.txt")
MD_DIR = os.path.join(BASE_DIR, "md")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# 确保目录存在
if not os.path.exists(MD_DIR):
    os.makedirs(MD_DIR)
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


class Preprocessor:
    def __init__(self, api_config=None):
        """
        Args:
            api_config: dict, 包含 'api_key', 'base_url', 'model_name', 'provider' 等配置
        """
        self.client = None
        self.api_config = api_config or {}

    def init_api(self):
        """仅在需要 API 时初始化"""
        if OpenAI is None:
            print("[Error] 未安装 openai 库。请运行: pip install openai")
            sys.exit(1)

        api_key = self.api_config.get("api_key", "")
        base_url = self.api_config.get("base_url", "")

        if not api_key:
            raise ValueError("API Key 未配置")
        if not base_url:
            raise ValueError("Base URL 未配置")

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _build_chat_url(self, base_url):
        base = (base_url or "").rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def _call_ai_api_simple(self, raw_text):
        """兼容模式：绕过 OpenAI SDK，直接 HTTP 调用"""
        api_key = self.api_config.get("api_key", "")
        base_url = self.api_config.get("base_url", "")
        if not api_key:
            raise ValueError("API Key 未配置")
        if not base_url:
            raise ValueError("Base URL 未配置")

        system_prompt = self.get_system_prompt()
        model_name = self.api_config.get("model_name", "gpt-3.5-turbo")

        url = self._build_chat_url(base_url)
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"以下是论文原始内容，请按要求处理：\n\n{raw_text}"},
            ],
            "temperature": 0.05,
            "stream": False,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_text = resp.read().decode("utf-8", errors="ignore")
                result = json.loads(resp_text)
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {e.code}: {detail}")
        except Exception as e:
            raise RuntimeError(str(e))

    def convert_to_plain_text(self, input_path):
        """步骤 1: 使用 Pandoc 将 docx/md/pdf 转换为纯文本"""
        print(f"[1/4] 正在读取并清洗原文件: {os.path.basename(input_path)}...")

        filename = os.path.basename(input_path)
        temp_txt_path = os.path.join(TEMP_DIR, f"{filename}.txt")

        # 构建 pandoc 命令：强制转换为 plain text
        cmd = f'pandoc "{input_path}" -t plain --wrap=none -o "{temp_txt_path}"'

        try:
            subprocess.run(cmd, shell=True, check=True)
            with open(temp_txt_path, "r", encoding="utf-8") as f:
                return f.read()
        except subprocess.CalledProcessError:
            print("[Error] Pandoc 转换失败，请检查是否安装 Pandoc。")
            sys.exit(1)
        except Exception as e:
            print(f"[Error] 读取文本失败: {e}")
            sys.exit(1)

    def get_system_prompt(self):
        """读取本地的 prompt.txt"""
        if not os.path.exists(PROMPT_FILE):
            print(f"[Error] 找不到提示词文件: {PROMPT_FILE}")
            sys.exit(1)
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def call_ai_api(self, raw_text):
        """API 模式: 直接调用接口"""
        print("[2/4] [API模式] 正在发送给 AI 进行排版 (请耐心等待)...")
        try:
            self.init_api()
        except Exception as e:
            if "proxies" in str(e):
                return self._call_ai_api_simple(raw_text)
            raise

        system_prompt = self.get_system_prompt()
        model_name = self.api_config.get("model_name", "gpt-3.5-turbo")

        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"以下是论文原始内容，请按要求处理：\n\n{raw_text}"},
                ],
                temperature=0.05,
                stream=False,
            )
            return response.choices[0].message.content
        except Exception as e:
            if "proxies" in str(e):
                return self._call_ai_api_simple(raw_text)
            print(f"[Error] AI API 调用失败: {e}")
            raise

    def prepare_web_mode(self, raw_text):
        """网页模式: 拼接 Prompt 并复制到剪切板"""
        print("[2/4] [网页模式] 正在生成提示词...")

        base_prompt = self.get_system_prompt()
        placeholder = "[在此处粘贴你的论文内容]"

        # 拼接完整内容
        if placeholder in base_prompt:
            full_content = base_prompt.replace(placeholder, raw_text)
        else:
            # 如果 prompt.txt 里没找到占位符，直接拼在后面
            full_content = base_prompt + "\n\n" + raw_text

        # 复制到剪切板
        try:
            pyperclip.copy(full_content)
            print("\n" + "=" * 50)
            print("✅ 已将 [提示词 + 论文内容] 复制到您的剪切板！")
            print("=" * 50)
            print("请执行以下步骤：")
            print("1. 打开 AI 网页端 (推荐 DeepSeek R1 / ChatGPT o1)")
            print("2. 💡 强烈建议开启【深度思考 (R1)】模式，排版效果更好")
            print("3. 在输入框按 Ctrl+V 粘贴并发送")
            print("4. 等待 AI 生成完毕后，点击【复制】按钮复制 AI 的回复")
            print("=" * 50)

            input("\n👉 当您已复制 AI 的回复后，请在此按回车键继续...")

            # 从剪切板读取 AI 的回复
            print("正在从剪切板读取内容...")
            ai_response = pyperclip.paste()

            if not ai_response or len(ai_response) < 10:
                print("[Warning] 剪切板内容似乎为空或太短，请确认您已复制 AI 的回复。")
                retry = input("是否重试读取剪切板? (y/n): ")
                if retry.lower() == "y":
                    ai_response = pyperclip.paste()
                else:
                    return None

            return ai_response

        except Exception as e:
            print(f"[Error] 剪切板操作失败: {e}")
            return None

    def split_and_save(self, ai_response, output_dir=None):
        """步骤 3: 解析 AI 返回的文本并拆分文件

        Args:
            ai_response: AI 返回的文本
            output_dir: 输出目录，如果为 None 则使用默认的 MD_DIR
        """
        if not ai_response:
            return False

        print("[3/4] 正在拆分并保存 Markdown 文件...")

        # 确定输出目录
        target_dir = output_dir if output_dir else MD_DIR
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        # ==================== 修复报错的关键部分 ====================
        # 原报错原因：正则表达式字符串必须用引号包裹，否则 Python 会把 ``` 当作语法错误
        # 修复后：使用 r'^...$' 格式

        # 1. 清洗：去掉可能存在的 markdown 代码块包裹
        # 去掉开头的 ```markdown 或 ```
        clean_response = re.sub(r"^```(markdown)?\s*", "", ai_response.strip())
        # 去掉结尾的 ```
        clean_response = re.sub(r"\s*```$", "", clean_response)
        # ==========================================================

        # 2. 正则匹配拆分
        pattern = r"===FILE:\s*(.*?)===\s*(.*?)(?=(===FILE:|$))"
        matches = re.findall(pattern, clean_response, re.DOTALL)

        if not matches:
            print("[Error] 无法解析 AI 返回的内容。")
            print("请检查 AI 是否严格按照 '===FILE: filename===' 格式输出。")
            # 调试用：将内容保存到 debug.txt 方便用户查看
            debug_path = os.path.join(TEMP_DIR, "debug_ai_response.txt")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(ai_response)
            print(f"已将原始内容保存至: {debug_path}")
            return False

        saved_files = []
        for filename, content, _ in matches:
            filename = filename.strip()
            content = content.strip()

            save_path = os.path.join(target_dir, filename)

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            saved_files.append(filename)
            print(f"   -> 已保存: {filename}")

        return len(saved_files) > 0

    def run_build_engine(self):
        """步骤 4: 调用构建脚本"""
        print("[4/4] 启动构建引擎 (build_engine.py)...")
        build_script = os.path.join(BASE_DIR, "build_engine.py")

        if os.path.exists(build_script):
            subprocess.run(["python", build_script])
        else:
            print(f"[Error] 找不到构建脚本: {build_script}")


def main():
    print("=" * 50)
    print("      SCAU 论文 AI 预处理助手")
    print("=" * 50)

    # 1. 获取输入文件
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = input("请输入原始论文文件路径 (docx/txt/md): ").strip().strip('"')

    if not os.path.exists(input_file):
        print("[Error] 文件不存在")
        return

    processor = Preprocessor()

    # 2. 选择模式
    print("\n请选择处理模式:")
    print("1. API 自动模式 (需配置 Key，全自动)")
    print("2. 网页端手动模式 (推荐 DeepSeek R1，效果好，免费)")
    mode = input("请输入选项 [2]: ").strip()

    # 3. 提取纯文本
    raw_text = processor.convert_to_plain_text(input_file)

    formatted_md = None
    if mode == "1":
        formatted_md = processor.call_ai_api(raw_text)
    else:
        # 默认为网页模式
        formatted_md = processor.prepare_web_mode(raw_text)

    # 4. 拆分与构建
    if formatted_md and processor.split_and_save(formatted_md):
        print("\n预处理完成！Markdown 文件已更新至 md/ 目录。")
        do_build = input("\n是否立即生成 Word 文档? (y/n) [y]: ").strip().lower()
        if do_build in ("", "y"):
            processor.run_build_engine()
    else:
        print("[Failed] 流程中止")


if __name__ == "__main__":
    main()
