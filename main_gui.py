import sys
import os
import time
import pyperclip
import tempfile
import shutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QPushButton, QTextEdit, QHBoxLayout, 
                             QGroupBox, QCheckBox, QRadioButton, QMessageBox,
                             QDialog, QFileDialog, QComboBox, QLineEdit, QFormLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont, QDesktopServices
import json
import urllib.request
import urllib.error

# ================= 导入后端模块 =================
# 确保这两个文件在同一目录下
import build_engine
from preprocess import Preprocessor

# ================= API 配置文件路径 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "api_config.json")
# 预设的 API 配置模板
API_PRESETS = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-5.2",
        "description": "OpenAI 官方 API"
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "model_name": "deepseek-reasoner",
        "description": "DeepSeek API (R1 深度思考模型)"
    },
    "Kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model_name": "moonshot-v1-8k",
        "description": "月之暗面 Kimi API"
    },
    "Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_name": "gemini-3-pro-preview",
        "description": "Google Gemini API (OpenAI 兼容格式)"
    },
    "Custom": {
        "base_url": "",
        "model_name": "",
        "description": "自定义中转站 / 其他 API"
    }
}

def load_api_config():
    """从文件加载 API 配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_api_config(config):
    """保存 API 配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False

# ================= 后台工作线程 =================
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
        self.user_confirmed = False # 用于网页模式的同步锁
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
            if self.mode == 'api':
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
                    "1. 请打开 AI 网页，点击下方你熟悉的AI快速跳转，或选择其他AI。\n"
                    "2. 待处理文本已复制到你的剪切板，粘贴（ctrl + v）发送给AI。\n"
                    "3. 等待AI生成完毕，复制 AI 的回复。\n"
                    "4. 复制好后，粘贴到下方的输入框内，再点击下方的【确定】按钮。"
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
                            "然后重新点击开始排版并选择保存路径。"
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
                self.log(f"🗑️ 已清理临时目录")
            except Exception as e:
                self.log(f"⚠️ 清理临时目录失败: {e}")


# ================= 自定义对话框：API 配置 =================
class ApiConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API 配置")
        self.setMinimumWidth(600)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 说明文字
        desc_label = QLabel("选择 AI 提供商并配置 API 信息，支持官方 API 和中转站：")
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont("微软雅黑", 10))
        layout.addWidget(desc_label)
        
        # 表单区域
        form = QFormLayout()
        form.setSpacing(10)
        
        # 提供商选择
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(API_PRESETS.keys())
        self.combo_provider.setFont(QFont("微软雅黑", 10))
        self.combo_provider.currentTextChanged.connect(self.on_provider_changed)
        form.addRow("AI 提供商:", self.combo_provider)
        
        # API Key
        self.edit_api_key = QLineEdit()
        self.edit_api_key.setPlaceholderText("输入你的 API Key")
        self.edit_api_key.setFont(QFont("微软雅黑", 10))
        self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API Key:", self.edit_api_key)
        
        # Base URL
        self.edit_base_url = QLineEdit()
        self.edit_base_url.setPlaceholderText("API 地址 (支持官方/中转站)")
        self.edit_base_url.setFont(QFont("微软雅黑", 10))
        form.addRow("Base URL:", self.edit_base_url)
        
        # 模型名称
        self.edit_model_name = QLineEdit()
        self.edit_model_name.setPlaceholderText("模型名称，如: gpt-4o")
        self.edit_model_name.setFont(QFont("微软雅黑", 10))
        form.addRow("模型名称:", self.edit_model_name)
        
        layout.addLayout(form)
        
        # 提示信息
        tip_label = QLabel(
            "💡 提示：\n"
            "• 如果使用中转站，请将 Base URL 改为中转站地址\n"
            "• 支持所有兼容 OpenAI 格式的 API\n"
            "• 配置会自动保存到本地"
        )
        tip_label.setWordWrap(True)
        tip_label.setFont(QFont("微软雅黑", 9))
        tip_label.setStyleSheet("color: #666; background-color: #f5f5f5; padding: 10px; border-radius: 5px;")
        layout.addWidget(tip_label)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_test = QPushButton("测试连接")
        btn_test.setFont(QFont("微软雅黑", 10))
        btn_test.clicked.connect(self.test_connection)
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setFont(QFont("微软雅黑", 10))
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("保存")
        btn_save.setFont(QFont("微软雅黑", 10))
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.save_config)
        
        btn_layout.addWidget(btn_test)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        # 加载现有配置
        self.load_config()
    
    def on_provider_changed(self, provider):
        """当选择提供商时，自动填充默认值"""
        config = load_api_config()
        providers = config.get("providers", {})

        if provider in providers:
            cfg = providers[provider]
            self.edit_api_key.setText(cfg.get("api_key", ""))
            self.edit_base_url.setText(cfg.get("base_url", ""))
            self.edit_model_name.setText(cfg.get("model_name", ""))
            return

        if provider in API_PRESETS:
            preset = API_PRESETS[provider]
            self.edit_api_key.clear()
            self.edit_base_url.setText(preset["base_url"])
            self.edit_model_name.setText(preset["model_name"])
    
    def load_config(self):
        """加载保存的配置"""
        config = load_api_config()
        if config:
            provider = config.get('provider', 'DeepSeek')
            if provider in API_PRESETS:
                self.combo_provider.setCurrentText(provider)

            providers = config.get('providers', {})
            if providers and provider in providers:
                cfg = providers[provider]
                self.edit_api_key.setText(cfg.get('api_key', ''))
                self.edit_base_url.setText(cfg.get('base_url', ''))
                self.edit_model_name.setText(cfg.get('model_name', ''))
                return

            # 兼容旧格式
            self.edit_api_key.setText(config.get('api_key', ''))
            self.edit_base_url.setText(config.get('base_url', ''))
            self.edit_model_name.setText(config.get('model_name', ''))
            return

        # 默认选择 DeepSeek
        self.combo_provider.setCurrentText('DeepSeek')
        self.on_provider_changed('DeepSeek')
    
    def get_config(self):
        """获取当前配置"""
        return {
            'provider': self.combo_provider.currentText(),
            'api_key': self.edit_api_key.text().strip(),
            'base_url': self.edit_base_url.text().strip(),
            'model_name': self.edit_model_name.text().strip()
        }
    
    def test_connection(self):
        """测试 API 连接"""
        config = self.get_config()
        
        if not config['api_key']:
            QMessageBox.warning(self, "提示", "请先输入 API Key")
            return
        if not config['base_url']:
            QMessageBox.warning(self, "提示", "请先输入 Base URL")
            return
        if not config['model_name']:
            QMessageBox.warning(self, "提示", "请先输入模型名称")
            return
        
        def _build_chat_url(base_url):
            base = (base_url or "").rstrip("/")
            if base.endswith("/v1"):
                return f"{base}/chat/completions"
            return f"{base}/v1/chat/completions"

        def _simple_test_request():
            url = _build_chat_url(config['base_url'])
            payload = {
                "model": config['model_name'],
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config['api_key']}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()

        try:
            from openai import OpenAI
        except Exception as e:
            try:
                _simple_test_request()
                QMessageBox.information(self, "成功", "✅ API 连接测试成功！")
                return
            except Exception as e2:
                QMessageBox.critical(self, "失败", f"❌ API 连接失败：\n\n{str(e2)}")
                return

        try:
            client = OpenAI(api_key=config['api_key'], base_url=config['base_url'])
            
            # 发送一个简单的测试请求
            client.chat.completions.create(
                model=config['model_name'],
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            
            QMessageBox.information(self, "成功", "✅ API 连接测试成功！")
        except Exception as e:
            if "proxies" in str(e):
                try:
                    _simple_test_request()
                    QMessageBox.information(self, "成功", "✅ API 连接测试成功！")
                    return
                except Exception as e2:
                    QMessageBox.critical(self, "失败", f"❌ API 连接失败：\n\n{str(e2)}")
                    return
            QMessageBox.critical(self, "失败", f"❌ API 连接失败：\n\n{str(e)}")
    
    def save_config(self):
        """保存配置"""
        config = self.get_config()
        
        if not config['api_key']:
            QMessageBox.warning(self, "提示", "请输入 API Key")
            return
        if not config['base_url']:
            QMessageBox.warning(self, "提示", "请输入 Base URL")
            return
        if not config['model_name']:
            QMessageBox.warning(self, "提示", "请输入模型名称")
            return
        
        existing = load_api_config()
        providers = existing.get("providers", {})
        providers[config['provider']] = {
            "api_key": config['api_key'],
            "base_url": config['base_url'],
            "model_name": config['model_name']
        }

        save_payload = {
            "provider": config['provider'],
            "providers": providers
        }

        if save_api_config(save_payload):
            QMessageBox.information(self, "成功", "配置已保存！")
            self.accept()
        else:
            QMessageBox.warning(self, "失败", "配置保存失败")


# ================= 自定义对话框：网页模式交互 =================
class WebModeDialog(QDialog):
    def __init__(self, parent=None, message=""):
        super().__init__(parent)
        self.setWindowTitle("网页模式操作")
        self.setMinimumSize(640, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        label = QLabel(message)
        label.setWordWrap(True)
        label.setFont(QFont("微软雅黑", 11))
        layout.addWidget(label)

        link_box = QGroupBox("AI 网页快捷入口")
        link_layout = QHBoxLayout()
        links = {
            "DeepSeek": "https://chat.deepseek.com/",
            "Kimi": "https://kimi.moonshot.cn/",
            "ChatGPT": "https://chat.openai.com/",
            "Gemini": "https://gemini.google.com/",
            "Claude": "https://claude.ai/",
        }
        for name, url in links.items():
            btn = QPushButton(name)
            btn.setFont(QFont("微软雅黑", 10))
            btn.clicked.connect(lambda _, u=url: QDesktopServices.openUrl(QUrl(u)))
            link_layout.addWidget(btn)
        link_box.setLayout(link_layout)
        layout.addWidget(link_box)

        input_label = QLabel("请先将提示词粘贴到网页对话框，等待 AI 处理完成后，再把结果复制到下面输入框：")
        input_label.setWordWrap(True)
        input_label.setFont(QFont("微软雅黑", 11))
        layout.addWidget(input_label)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("在此粘贴 AI 返回的完整内容...")
        self.input_text.setFont(QFont("微软雅黑", 10))
        self.input_text.setMinimumHeight(160)
        layout.addWidget(self.input_text)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_ok = QPushButton("确定")
        btn_ok.setDefault(True)
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _on_ok(self):
        if len(self.input_text.toPlainText().strip()) < 10:
            QMessageBox.warning(self, "提示", "请粘贴 AI 返回的完整内容后再继续。")
            return
        self.accept()

    def get_text(self):
        return self.input_text.toPlainText().strip()


# ================= 自定义控件：拖拽区域 =================
class DropArea(QLabel):
    file_dropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setText("📂\n\n将论文文件拖拽至此\n(支持 .docx / .md / .txt)")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("微软雅黑", 13))
        # CSS 样式：虚线边框，圆角
        self.setStyleSheet("""
            QLabel {
                border: 3px dashed #aaa;
                border-radius: 15px;
                background-color: #f0f0f0;
                color: #555;
            }
            QLabel:hover {
                border-color: #4CAF50;
                background-color: #e8f5e9;
                color: #2E7D32;
            }
        """)
        self.setAcceptDrops(True) # 开启拖拽支持

    def dragEnterEvent(self, event: QDragEnterEvent):
        # 只有拖入文件时才接受
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        # 获取文件路径
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if not files:
            return

        allowed_exts = {".docx", ".md", ".txt"}

        # 支持一次拖入多个时：选择第一个合法文件
        for path in files:
            if not path:
                continue
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext in allowed_exts:
                self.file_dropped.emit(path)
                return

        # 没有任何合法文件
        QMessageBox.warning(
            self,
            "不支持的文件类型",
            "仅支持拖入 .docx / .md / .txt 文件。\n\n"
            "你拖入的内容不属于以上格式。",
        )


# ================= 主窗口 =================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCAU 论文自动化排版工具 v2.0 (GUI版)")
        self.resize(700, 800)
        self.input_file = None
        
        # 初始化界面布局
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. 拖拽区域
        self.drop_area = DropArea()
        self.drop_area.file_dropped.connect(self.on_file_loaded)
        self.drop_area.setFixedHeight(180)
        main_layout.addWidget(self.drop_area)

        # 2. 文件路径显示
        self.lbl_path = QLabel("当前未选择文件")
        self.lbl_path.setStyleSheet("color: #666; font-size: 13px;")
        self.lbl_path.setWordWrap(True)
        main_layout.addWidget(self.lbl_path)

        # 3. 模式选择 (Radio Buttons)
        grp_mode = QGroupBox("第一步：选择处理模式")
        grp_mode.setFont(QFont("微软雅黑", 11, QFont.Weight.Bold))
        layout_mode = QHBoxLayout()
        
        self.rb_web = QRadioButton("网页手动模式 (推荐 DeepSeek R1 / ChatGPT)")
        self.rb_api = QRadioButton("API 自动模式 (需配置 Key)")
        self.rb_web.setFont(QFont("微软雅黑", 10))
        self.rb_api.setFont(QFont("微软雅黑", 10))
        self.rb_web.setChecked(True) # 默认选中网页模式
        
        layout_mode.addWidget(self.rb_web)
        layout_mode.addWidget(self.rb_api)
        
        # API 配置按钮
        self.btn_api_config = QPushButton("⚙️ API 配置")
        self.btn_api_config.setFont(QFont("微软雅黑", 10))
        self.btn_api_config.setFixedWidth(120)
        self.btn_api_config.clicked.connect(self.open_api_config)
        self.btn_api_config.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        layout_mode.addWidget(self.btn_api_config)
        
        grp_mode.setLayout(layout_mode)
        main_layout.addWidget(grp_mode)

        # 4. 组件选择 (Checkboxes)
        grp_comp = QGroupBox("第二步：选择组装内容")
        grp_comp.setFont(QFont("微软雅黑", 11, QFont.Weight.Bold))
        layout_comp = QVBoxLayout()
        
        # 动态读取 build_engine 中的注册表
        self.checks = {}
        # 强制定义一个好看的显示顺序
        display_order = ["cover", "originality", "abs_cn", "abs_en",  "symbols","toc", "body"]
        
        # 网格布局：每行放3个
        row_layout = QHBoxLayout()
        count = 0
        
        for key in display_order:
            if key in build_engine.COMPONENT_REGISTRY:
                item = build_engine.COMPONENT_REGISTRY[key]
                cb = QCheckBox(item['desc']) # 显示中文描述
                cb.setChecked(True)          # 默认全选
                cb.setFont(QFont("微软雅黑", 10))
                self.checks[key] = cb
                
                row_layout.addWidget(cb)
                count += 1
                
                # 每3个换一行
                if count % 3 == 0:
                    layout_comp.addLayout(row_layout)
                    row_layout = QHBoxLayout()
        
        # 把最后一行没满的加上去
        if count % 3 != 0:
            layout_comp.addLayout(row_layout)

        grp_comp.setLayout(layout_comp)
        main_layout.addWidget(grp_comp)

        # 5. 开始按钮
        self.btn_start = QPushButton("开始排版")
        self.btn_start.setFixedHeight(50)
        self.btn_start.setFont(QFont("微软雅黑", 13, QFont.Weight.Bold))
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; 
                color: white; 
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #B0BEC5; }
        """)
        self.btn_start.clicked.connect(self.start_process)
        main_layout.addWidget(self.btn_start)

        # 6. 日志输出框
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("运行日志将显示在这里...")
        self.txt_log.setFont(QFont("Consolas", 10))
        self.txt_log.setStyleSheet("""
            QTextEdit {
                background-color: #263238; 
                color: #80CBC4; 
                font-family: Consolas, monospace;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        main_layout.addWidget(self.txt_log)

    def open_api_config(self):
        """打开 API 配置对话框"""
        dialog = ApiConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.log("API 配置已更新")
    
    def on_file_loaded(self, path):
        self.input_file = path
        self.lbl_path.setText(f"✅ 已加载: {path}")
        self.drop_area.setText("📄\n文件已就绪")
        self.drop_area.setStyleSheet("""
            QLabel {
                border: 3px solid #4CAF50;
                border-radius: 15px;
                background-color: #e8f5e9;
                color: #2E7D32;
            }
        """)
        self.log(f"文件已加载: {path}")

    def log(self, text):
        self.txt_log.append(text)
        # 自动滚动到底部
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def is_file_locked(self, filepath):
        """检查文件是否被占用（尝试以追加模式打开）"""
        if not os.path.exists(filepath):
            return False
        try:
            # 尝试以追加模式打开文件
            # 如果文件被 Word 打开，这里通常会抛出 PermissionError
            with open(filepath, 'a'):
                pass
            return False
        except PermissionError:
            return True
        except Exception:
            return False

    def start_process(self):
        if not self.input_file:
            QMessageBox.warning(self, "提示", "请先拖入论文文件！")
            return

        # === 新增：文件占用检测（启动 Worker 前做） ===
        if self.is_file_locked(self.input_file):
            QMessageBox.critical(
                self,
                "无法访问文件",
                f"检测到文件正在被使用：\n{self.input_file}\n\n"
                "请先关闭 Microsoft Word 或其他占用该文件的程序，然后再试。",
            )
            return

        # 获取选中的组件 Key
        selected_keys = [k for k, cb in self.checks.items() if cb.isChecked()]
        if not selected_keys:
            QMessageBox.warning(self, "提示", "请至少勾选一个组件！")
            return

        # 锁定按钮
        self.btn_start.setEnabled(False)
        self.btn_start.setText("正在处理中...")
        self.txt_log.clear()

        mode = 'api' if self.rb_api.isChecked() else 'web'
        
        # 如果是 API 模式，检查配置
        api_config = None
        if mode == 'api':
            raw_config = load_api_config()
            if raw_config.get("providers") and raw_config.get("provider"):
                provider = raw_config.get("provider")
                api_config = raw_config.get("providers", {}).get(provider, {})
            else:
                api_config = raw_config

            if not api_config or not api_config.get('api_key'):
                QMessageBox.warning(self, "提示", "请先配置 API 信息！\n点击【⚙️ API 配置】按钮进行设置。")
                self.btn_start.setEnabled(True)
                self.btn_start.setText("开始排版")
                return

        # 启动线程
        self.worker = WorkerThread(self.input_file, mode, selected_keys, api_config)
        self.worker.log_signal.connect(self.log)
        self.worker.finish_signal.connect(self.on_finish)
        self.worker.ask_user_signal.connect(self.on_ask_user)
        self.worker.ask_save_signal.connect(self.on_ask_save)
        self.worker.error_signal.connect(self.on_worker_error)
        self.worker.start()

    def on_worker_error(self, title, message):
        QMessageBox.warning(self, title, message)

    def on_ask_user(self, msg):
        """处理网页模式的弹窗交互"""
        dialog = WebModeDialog(self, msg)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.worker.confirm_continue(dialog.get_text())
        else:
            self.worker.confirm_continue("")

    def on_ask_save(self, default_name):
        """让用户选择保存路径与文件名"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择保存位置",
            os.path.abspath(default_name),
            "Word 文档 (*.docx)"
        )
        self.worker.set_save_path(path)

    def on_finish(self, success):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("开始排版")
        if success:
            QMessageBox.information(self, "成功", "文档生成成功！\n请查看项目目录下的 Output_xxxx.docx")
        else:
            QMessageBox.warning(self, "失败", "排版过程中出现错误，请查看下方日志。")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置全局字体，防止某些系统显示模糊
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())