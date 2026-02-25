import os
import sys
import json
import urllib.request
import urllib.error

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QGroupBox,
    QTextEdit,
)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QDesktopServices, QPixmap

from core import config_manager


def resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境和 PyInstaller 打包环境"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, relative_path)


class ConnectionTesterThread(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

    def run(self):
        def _build_chat_url(base_url):
            base = (base_url or "").rstrip("/")
            if base.endswith("/v1"):
                return f"{base}/chat/completions"
            return f"{base}/v1/chat/completions"

        def _simple_test_request():
            url = _build_chat_url(self.config["base_url"])
            payload = {
                "model": self.config["model_name"],
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }
            import json, urllib.request
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config['api_key']}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()

        try:
            from openai import OpenAI
        except Exception:
            try:
                _simple_test_request()
                self.finished_signal.emit(True, "✅ API 连接测试成功！")
                return
            except Exception as e2:
                self.finished_signal.emit(False, f"❌ API 连接失败：\n\n{str(e2)}")
                return

        try:
            client = OpenAI(api_key=self.config["api_key"], base_url=self.config["base_url"])
            client.chat.completions.create(
                model=self.config["model_name"],
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            self.finished_signal.emit(True, "✅ API 连接测试成功！")
        except Exception as e:
            if "proxies" in str(e):
                try:
                    _simple_test_request()
                    self.finished_signal.emit(True, "✅ API 连接测试成功！")
                    return
                except Exception as e2:
                    self.finished_signal.emit(False, f"❌ API 连接失败：\n\n{str(e2)}")
                    return
            self.finished_signal.emit(False, f"❌ API 连接失败：\n\n{str(e)}")


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
        self.combo_provider.addItems(config_manager.get_api_presets().keys())
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
        tip_label.setStyleSheet(
            "color: #666; background-color: #f5f5f5; padding: 10px; border-radius: 5px;"
        )
        layout.addWidget(tip_label)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_test = QPushButton("测试连接")
        self.btn_test.setFont(QFont("微软雅黑", 10))
        self.btn_test.clicked.connect(self.test_connection)

        btn_cancel = QPushButton("取消")
        btn_cancel.setFont(QFont("微软雅黑", 10))
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("保存")
        btn_save.setFont(QFont("微软雅黑", 10))
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.save_config)

        btn_layout.addWidget(self.btn_test)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        # 加载现有配置
        self.load_config()

    def on_provider_changed(self, provider):
        """当选择提供商时，自动填充默认值"""
        config = config_manager.load_api_config()
        providers = config.get("providers", {})

        if provider in providers:
            cfg = providers[provider]
            self.edit_api_key.setText(cfg.get("api_key", ""))
            self.edit_base_url.setText(cfg.get("base_url", ""))
            self.edit_model_name.setText(cfg.get("model_name", ""))
            return

        presets = config_manager.get_api_presets()
        if provider in presets:
            preset = presets[provider]
            self.edit_api_key.clear()
            self.edit_base_url.setText(preset["base_url"])
            self.edit_model_name.setText(preset["model_name"])

    def load_config(self):
        """加载保存的配置"""
        config = config_manager.load_api_config()
        presets = config_manager.get_api_presets()
        if config:
            provider = config.get("provider", "DeepSeek")
            if provider in presets:
                self.combo_provider.setCurrentText(provider)

            providers = config.get("providers", {})
            if providers and provider in providers:
                cfg = providers[provider]
                self.edit_api_key.setText(cfg.get("api_key", ""))
                self.edit_base_url.setText(cfg.get("base_url", ""))
                self.edit_model_name.setText(cfg.get("model_name", ""))
                return

            # 兼容旧格式
            self.edit_api_key.setText(config.get("api_key", ""))
            self.edit_base_url.setText(config.get("base_url", ""))
            self.edit_model_name.setText(config.get("model_name", ""))
            return

        # 默认选择 DeepSeek
        self.combo_provider.setCurrentText("DeepSeek")
        self.on_provider_changed("DeepSeek")

    def get_config(self):
        """获取当前配置"""
        return {
            "provider": self.combo_provider.currentText(),
            "api_key": self.edit_api_key.text().strip(),
            "base_url": self.edit_base_url.text().strip(),
            "model_name": self.edit_model_name.text().strip(),
        }

    def test_connection(self):
        """测试 API 连接"""
        config = self.get_config()

        if not config["api_key"]:
            QMessageBox.warning(self, "提示", "请先输入 API Key")
            return
        if not config["base_url"]:
            QMessageBox.warning(self, "提示", "请先输入 Base URL")
            return
        if not config["model_name"]:
            QMessageBox.warning(self, "提示", "请先输入模型名称")
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("正在测试...")

        self.tester_thread = ConnectionTesterThread(config, self)
        self.tester_thread.finished_signal.connect(self.on_test_finished)
        self.tester_thread.start()

    def on_test_finished(self, success, message):
        self.btn_test.setEnabled(True)
        self.btn_test.setText("测试连接")
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "失败", message)

    def save_config(self):
        """保存配置"""
        config = self.get_config()

        if not config["api_key"]:
            QMessageBox.warning(self, "提示", "请输入 API Key")
            return
        if not config["base_url"]:
            QMessageBox.warning(self, "提示", "请输入 Base URL")
            return
        if not config["model_name"]:
            QMessageBox.warning(self, "提示", "请输入模型名称")
            return

        existing = config_manager.load_api_config()
        providers = existing.get("providers", {})
        providers[config["provider"]] = {
            "api_key": config["api_key"],
            "base_url": config["base_url"],
            "model_name": config["model_name"],
        }

        save_payload = {"provider": config["provider"], "providers": providers}

        if config_manager.save_api_config(save_payload):
            QMessageBox.information(self, "成功", "配置已保存！")
            self.accept()
        else:
            QMessageBox.warning(self, "失败", "配置保存失败")


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
            "Grok": "https://grok.com/",
            "Claude": "https://claude.ai/",
            "豆包": "https://www.doubao.com/chat/",
            "千问": "https://chat.qwen.ai/",
            "Google AI Studio": "https://ai.google.com/studio",
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
        self.input_text.setPlaceholderText("在此粘贴（ctrl + v） AI 返回的完整内容...")
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


