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

    def __init__(
        self,
        input_path,
        mode,
        components,
        api_config=None,
        output_dir: str | None = None,
        output_basename: str | None = None,
        export_docx: bool = True,
        export_pdf: bool = False,
    ):
        super().__init__()
        self.input_path = input_path
        self.mode = mode  # 'api' 或 'web'
        self.components = components
        self.api_config = api_config or {}  # API 配置
        self.user_confirmed = False  # 用于网页模式的同步锁
        self.user_response = None
        self.save_path = None
        self.temp_md_dir = None  # 临时目录路径

        # 导出设置
        self.output_dir = (output_dir or "").strip() or None
        self.output_basename = (output_basename or "").strip() or None
        self.export_docx = bool(export_docx)
        self.export_pdf = bool(export_pdf)

    def _sanitize_filename(self, name: str) -> str:
        """Windows 文件名清理：去掉不允许字符"""
        invalid = '<>:/\\|?*"'
        cleaned = "".join(("_" if ch in invalid else ch) for ch in (name or ""))
        cleaned = cleaned.strip().strip(".")
        return cleaned

    def _is_file_locked(self, filepath: str) -> bool:
        if not filepath or not os.path.exists(filepath):
            return False
        try:
            with open(filepath, "a"):
                pass
            return False
        except PermissionError:
            return True
        except Exception:
            return False

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

                try:
                    # 调用构建器，先输出到临时文件
                    if not self.export_docx and not self.export_pdf:
                        self.log("❌ 未选择任何导出格式（docx/pdf），流程终止。")
                        self.finish_signal.emit(False)
                        return

                    # 5. 计算输出路径（可自定义目录；留空默认 outputs）
                    outputs_root = build_engine.Config.OUTPUTS_DIR
                    os.makedirs(outputs_root, exist_ok=True)

                    final_dir = (self.output_dir or "").strip()
                    if not final_dir:
                        final_dir = outputs_root
                    # 相对路径默认放到 outputs 下
                    if not os.path.isabs(final_dir):
                        final_dir = os.path.abspath(os.path.join(outputs_root, final_dir))
                    os.makedirs(final_dir, exist_ok=True)

                    base = self.output_basename
                    if not base:
                        base = os.path.splitext(os.path.basename(self.input_path))[0]
                    base = self._sanitize_filename(base) or f"Output_{int(time.time())}"

                    final_docx = os.path.join(final_dir, f"{base}.docx") if self.export_docx else None
                    final_pdf = os.path.join(final_dir, f"{base}.pdf") if self.export_pdf else None

                    # 输出占用检测
                    for target in [p for p in [final_docx, final_pdf] if p]:
                        if self._is_file_locked(target):
                            self.log(f"❌ 输出失败：目标文件被占用: {os.path.basename(target)}")
                            self.error_signal.emit(
                                "输出失败（文件被占用）",
                                "检测到目标文件可能正在被 Word/其他程序占用：\n\n"
                                f"{target}\n\n"
                                "请先关闭占用程序后重试。",
                            )
                            self.finish_signal.emit(False)
                            return

                    # 6. 构建：docx 可能是最终文件，也可能只是 pdf 的临时中间产物
                    docx_build_path = final_docx or os.path.join(self.temp_md_dir, f"{base}_temp.docx")
                    self.log("🔧 正在生成 Word 文档...")
                    builder.build(
                        self.components,
                        docx_build_path,
                        output_pdf_filename=final_pdf,
                        component_registry=local_registry,
                    )

                    # 兼容：如果仅导出 pdf，不保留中间 docx
                    if not self.export_docx:
                        try:
                            if os.path.exists(docx_build_path):
                                os.remove(docx_build_path)
                        except Exception:
                            pass

                    outputs = [p for p in [final_docx, final_pdf] if p]
                    self.log("✅ 导出完成：")
                    for p in outputs:
                        self.log(f"- {os.path.abspath(p)}")
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
