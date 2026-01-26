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
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QDesktopServices, QPixmap

from core import config_manager


def resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境和 PyInstaller 打包环境"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, relative_path)


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

        def _build_chat_url(base_url):
            base = (base_url or "").rstrip("/")
            if base.endswith("/v1"):
                return f"{base}/chat/completions"
            return f"{base}/v1/chat/completions"

        def _simple_test_request():
            url = _build_chat_url(config["base_url"])
            payload = {
                "model": config["model_name"],
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config['api_key']}",
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
                QMessageBox.information(self, "成功", "✅ API 连接测试成功！")
                return
            except Exception as e2:
                QMessageBox.critical(self, "失败", f"❌ API 连接失败：\n\n{str(e2)}")
                return

        try:
            client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])

            # 发送一个简单的测试请求
            client.chat.completions.create(
                model=config["model_name"],
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
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


class TutorialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SCAU 论文排版助手 - 新手引导")
        self.resize(950, 680)  # 稍微调大一点，为了展示对比图的细节
        self.current_step = 0

        # 读取主题（用于修正本对话框里“硬编码白色”的样式）
        self.current_theme = config_manager.get_theme("light")

        # === 修改核心：增加了前4个对比步骤 ===
        self.steps = [
            # --- 阶段一：痛点展示 (排版前) ---
            {
                "img": "未排版的文档docx.png",
                "title": "排版前：杂乱无章的 Word 草稿",
                "text": "你是否还在为格式发愁？\n"
                "字体大小不一、行距混乱、图片没居中、引用格式错误……\n"
                "手动修改这些细节通常需要耗费数小时。",
            },
            {
                "img": "未排版的文档txt.png",
                "title": "排版前：哪怕是纯文本也能搞定",
                "text": "即使你只有一份用记事本写的 .txt 纯文本，或者 Markdown 文件，\n"
                "完全没有样式，本工具也能识别并处理。",
            },

            # --- 阶段二：效果展示 (排版后) ---
            {
                "img": "排版好的文档1.png",
                "title": "排版后：一键生成标准封面与摘要",
                "text": "使用本工具处理后：\n"
                "✅ 封面、原创性声明自动生成，信息准确。\n"
                "✅ 中英文摘要字体、字号、悬挂缩进严格符合学校规范。",
            },
            {
                "img": "排版好的文档2.png",
                "title": "排版后：完美的目录与正文格式",
                "text": "✅ 目录自动生成（带页码跳转）。\n"
                "✅ 正文三级标题自动编号。\n"
                "✅ 图片自动居中，三线表格式自动调整。\n"
                "✅ 参考文献自动生成并按标准格式引用。",
            },

            # --- 阶段三：操作教程 (原有步骤) ---
            {
                "img": "step1.png",
                "title": "教程第1步：加载文件与模式选择",
                "text": "1. 将你的原稿（.docx / .txt）直接拖入上方的虚线框内。\n"
                "2. 勾选“网页手动模式”（推荐使用 DeepSeek）。\n"
                "3. 勾选你需要的组件（封面、正文等），点击【开始排版】。",
            },
            {
                "img": "step2.png",
                "title": "教程第2步：获取提示词与跳转",
                "text": "1. 软件会自动生成“提示词+论文内容”并复制到你的剪切板。\n"
                "2. 点击弹窗中的快捷按钮（如 DeepSeek），浏览器会自动打开 AI 网站。\n"
                "3. 此时保持本软件不要关闭，去浏览器进行下一步操作。",
            },
            {
                "img": "step3.png",
                "title": "教程第3步：AI 处理（关键）",
                "text": "1. 在 AI 对话框中，直接按 Ctrl+V 粘贴刚刚复制的内容。\n"
                "2. 强烈建议开启“深度思考”模式，排版逻辑更严密。\n"
                "3. 点击发送，耐心等待 AI 输出完毕。",
            },
            {
                "img": "step4.png",
                "title": "教程第4步：回填结果",
                "text": "1. 待 AI 输出完成后，点击 AI 界面下方的【复制】图标。\n"
                "2. 回到本软件，将内容粘贴到输入框中。\n"
                "3. 点击【确定】，软件将自动开始生成最终的 Word 文档。",
            },
        ]

        self.init_ui()
        self.update_content()

    def init_ui(self):
        # 保持之前的 UI 代码不变
        layout = QVBoxLayout(self)

        # 1. 图片展示区
        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.current_theme == "dark":
            self.lbl_image.setStyleSheet(
                "background-color: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 8px;"
            )
        else:
            self.lbl_image.setStyleSheet(
                "background-color: #f0f0f0; border: 1px solid #ddd; border-radius: 8px;"
            )
        # 图片区域稍微留大一点
        self.lbl_image.setMinimumSize(900, 500)
        layout.addWidget(self.lbl_image)

        # 2. 文字说明区
        text_container = QVBoxLayout()
        self.lbl_title = QLabel()
        self.lbl_title.setFont(QFont("微软雅黑", 14, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #2196F3;")

        self.lbl_text = QLabel()
        self.lbl_text.setFont(QFont("微软雅黑", 11))
        self.lbl_text.setWordWrap(True)

        text_container.addWidget(self.lbl_title)
        text_container.addWidget(self.lbl_text)
        layout.addLayout(text_container)

        # 3. 底部按钮区
        btn_layout = QHBoxLayout()
        self.btn_prev = QPushButton("上一步")
        self.btn_next = QPushButton("下一步")

        for btn in [self.btn_prev, self.btn_next]:
            btn.setFixedHeight(40)
            btn.setFont(QFont("微软雅黑", 10))
            btn.setMinimumWidth(100)

        self.btn_prev.clicked.connect(self.prev_step)
        self.btn_next.clicked.connect(self.next_step)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_prev)
        btn_layout.addWidget(self.btn_next)
        layout.addLayout(btn_layout)

    def update_content(self):
        """根据 current_step 更新界面"""
        data = self.steps[self.current_step]

        # 更新文字
        step_indicator = f"({self.current_step + 1}/{len(self.steps)}) "
        self.lbl_title.setText(step_indicator + data["title"])
        self.lbl_text.setText(data["text"])

        # 更新图片
        img_path = resource_path(os.path.join("引导", data["img"]))

        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            # 图片自适应缩放，保持比例
            if not pixmap.isNull():
                scaled_pix = pixmap.scaled(
                    self.lbl_image.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.lbl_image.setPixmap(scaled_pix)
            else:
                self.lbl_image.setText("图片加载失败")
        else:
            self.lbl_image.setText(f"图片丢失: {data['img']}\n请确保图片在'引导'文件夹内")

        # 更新按钮状态
        self.btn_prev.setEnabled(self.current_step > 0)

        if self.current_step == len(self.steps) - 1:
            self.btn_next.setText("开启排版之旅")
            self.btn_next.setStyleSheet(
                "background-color: #4CAF50; color: white; font-weight: bold; border-radius: 5px;"
            )
        else:
            self.btn_next.setText("下一步")
            if self.current_theme == "dark":
                self.btn_next.setStyleSheet(
                    "QPushButton { border-radius: 5px; border: 1px solid #3A3A3A; background-color: #1E1E1E; color: #EAEAEA; } "
                    "QPushButton:hover { background-color: #262626; }"
                )
            else:
                self.btn_next.setStyleSheet(
                    "QPushButton { border-radius: 5px; border: 1px solid #ccc; background-color: #fff; } "
                    "QPushButton:hover { background-color: #eee; }"
                )

    def next_step(self):
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            self.update_content()
        else:
            self.accept()

    def prev_step(self):
        if self.current_step > 0:
            self.current_step -= 1
            self.update_content()
