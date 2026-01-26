import os
import time
import tempfile
import shutil
import pyperclip
from PyQt6.QtCore import QThread, pyqtSignal

from .preprocess import Preprocessor
from . import build_engine


class WorkerThread(QThread):
    """
    后台线程：负责执行耗时的 IO 操作、AI 请求和 Word 生成
    避免主界面卡死
    """
    log_signal = pyqtSignal(str)       # 发送日志到界面
    finish_signal = pyqtSignal(bool)   # 任务结束信号
    ask_user_signal = pyqtSignal(str)  # 请求用户操作信号 (用于网页模式)
    ask_save_signal = pyqtSignal(str)  # 请求保存路径信号
    error_signal = pyqtSignal(str, str)  # 错误提示弹窗（标题, 内容）

    def __init__(self, input_path, mode, components, api_config=None):
        super().__init__()
        self.input_path = input_path
        self.mode = mode  # 'api' 或 'web'
        self.components = components
        self.api_config = api_config or {}  # API 配置
        self.user_confirmed = False  # 用于网页模式的同步锁
        self.user_response = None
        self.save_path = None
        self.temp_md_dir = None  # 临时目录路径

    def log(self, text):
        self.log_signal.emit(text)

    def run(self):
        try:
            processor = Preprocessor(api_config=self.api_config)
            builder = build_engine.DocumentBuilder()

            # 创建临时目录用于存放拆分的 markdown 文件
            self.temp_md_dir = tempfile.mkdtemp(prefix="autoformatter_")
            self.log(f"📁 已创建临时目录: {self.temp_md_dir}")

            # 1. 转纯文本
            self.log(f"📄 正在读取文件: {os.path.basename(self.input_path)}...")
            raw_text = processor.convert_to_plain_text(self.input_path)

            formatted_md = None

            # 2. AI 处理阶段
            if self.mode == "api":
                self.log("🤖 [API模式] 正在调用 AI 进行排版 (请耐心等待)...")
                try:
                    # 如果你没有配置 API Key，这里会报错
                    formatted_md = processor.call_ai_api(raw_text)
                except Exception as e:
                    self.log(f"❌ API 调用失败: {e}")
                    self._cleanup_temp_dir()
                    self.finish_signal.emit(False)
                    return
            else:
                # === 网页模式逻辑 ===
                self.log("🔗 [网页模式] 正在生成提示词...")
                base_prompt = processor.get_system_prompt()

                # 拼接提示词
                if "[在此处粘贴你的论文内容]" in base_prompt:
                    full_content = base_prompt.replace("[在此处粘贴你的论文内容]", raw_text)
                else:
                    full_content = base_prompt + "\n\n" + raw_text

                # 复制到剪切板
                pyperclip.copy(full_content)
                self.log("✅ 提示词已复制到剪切板！")

                # 发送信号给主界面，弹窗提示用户
                msg = (
                    "你现在要做的事情：\n"
                    "1. 选择下方任何一个你熟悉的AI，打开深度思考模式。\n"
                    "2. 在对话框直接按粘贴（ctrl + v）发送给AI。你不需要在意发送了什么，这部分工具已自动帮你处理好。\n"
                    "3. 等待AI生成完毕，复制 AI 的回复。\n"
                    "4. 复制好后，粘贴到这个工具下方的输入框内，再点击下方的【确定】按钮。"
                )
                self.ask_user_signal.emit(msg)

                # === 线程阻塞，等待用户点击确定 ===
                while not self.user_confirmed:
                    time.sleep(0.5)

                self.log("📋 正在读取用户粘贴的内容...")
                formatted_md = (self.user_response or "").strip()

                if not formatted_md or len(formatted_md) < 10:
                    self.log("❌ 输入内容为空或无效，流程终止。")
                    self._cleanup_temp_dir()
                    self.finish_signal.emit(False)
                    return

            # 3. 拆分文件到临时目录
            self.log("✂️ 正在拆分 Markdown 文件到临时目录...")
            if processor.split_and_save(formatted_md, output_dir=self.temp_md_dir):
                self.log("✅ Markdown 拆分完成。")

                # 4. 组装 Word 文档到临时位置
                self.log(f"🔨 正在组装 Word 文档 (包含: {len(self.components)} 个组件)...")

                # 构造局部 registry，覆盖 markdown 文件路径（避免修改全局 COMPONENT_REGISTRY，线程更安全）
                local_registry = {k: dict(v) for k, v in build_engine.COMPONENT_REGISTRY.items()}
                for key in ["abs_cn", "abs_en", "body"]:
                    if key in local_registry:
                        original_path = local_registry[key].get("path", "")
                        filename = os.path.basename(original_path) if original_path else ""
                        if filename:
                            local_registry[key]["path"] = os.path.join(self.temp_md_dir, filename)

                temp_output = os.path.join(self.temp_md_dir, "temp_output.docx")

                try:
                    # 调用构建器，先输出到临时文件
                    builder.build(self.components, temp_output, component_registry=local_registry)
                    self.log("✅ Word 文档组装完成！")

                    # 5. 现在让用户选择最终保存位置
                    default_name = f"Output_{int(time.time())}.docx"
                    self.ask_save_signal.emit(default_name)

                    while self.save_path is None:
                        time.sleep(0.2)

                    if not self.save_path:
                        self.log("❌ 用户取消保存，流程终止。")
                        self.finish_signal.emit(False)
                        return

                    # 6. 复制临时文件到用户选择的位置
                    self.log(f"📦 正在保存文档到: {os.path.basename(self.save_path)}...")
                    try:
                        shutil.copy2(temp_output, self.save_path)
                    except PermissionError:
                        self.log("❌ 保存失败：目标文件可能正在被占用（常见于 Word 已打开同名文档）。")
                        self.error_signal.emit(
                            "保存失败（文件被占用）",
                            "检测到目标 .docx 可能正在被 Word 占用。\n\n"
                            "请你先手动关闭已打开的 Word 文档（不要让程序代替你关闭，以免丢失未保存内容），\n"
                            "然后重新点击开始排版并选择保存路径。",
                        )
                        self.finish_signal.emit(False)
                        return

                    self.log(f"🎉 全部完成！\n输出文件: {os.path.abspath(self.save_path)}")
                    self.finish_signal.emit(True)

                finally:
                    # 清理临时目录
                    self._cleanup_temp_dir()

            else:
                self.log("❌ 文件拆分失败，请检查 AI 返回格式是否包含 ===FILE: ...===")
                self._cleanup_temp_dir()
                self.finish_signal.emit(False)

        except Exception as e:
            self.log(f"❌ 发生严重错误: {str(e)}")
            import traceback

            self.log(traceback.format_exc())
            self._cleanup_temp_dir()
            self.finish_signal.emit(False)

    def confirm_continue(self, response_text):
        """主界面弹窗点击确定后，调用此方法解锁线程"""
        self.user_response = response_text
        self.user_confirmed = True

    def set_save_path(self, path):
        self.save_path = path

    def _cleanup_temp_dir(self):
        """清理临时目录"""
        if self.temp_md_dir and os.path.exists(self.temp_md_dir):
            try:
                shutil.rmtree(self.temp_md_dir)
                self.log("🗑️ 已清理临时目录")
            except Exception as e:
                self.log(f"⚠️ 清理临时目录失败: {e}")
