import os
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QGroupBox,
    QCheckBox,
    QRadioButton,
    QMessageBox,
    QDialog,
    QFileDialog,
    QComboBox,
    QLineEdit,
)
from PyQt6.QtWidgets import QButtonGroup
from PyQt6.QtGui import QFont

from core import build_engine
from core import config_manager
from core.worker import WorkerThread
from .widgets import DropArea
from .dialogs import ApiConfigDialog, WebModeDialog
from .styles import global_stylesheet
from .overlay_tour import OverlayTour

# ================= 组件预设配置 =================
# Key 对应 build_engine.COMPONENT_REGISTRY 的键
PRESETS = {
    "thesis": ["cover", "originality", "abs_cn", "abs_en", "symbols", "toc", "body"],
    "paper": ["cover", "abs_cn", "body"],
    "report": ["cover_exp", "toc", "body"],
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCAU 论文自动化排版工具")
        self.resize(750, 850)
        self.input_file = None

        # 主题设置（持久化）
        self.current_theme = config_manager.get_theme("light")

        # 组件预设（可按需扩展）
        self.PRESETS = PRESETS
        self._suppress_preset_sync = False

        # 初始化界面布局
        self.init_ui()

        # 应用主题（放在 init_ui 后，确保控件已创建）
        self.apply_theme(self.current_theme)

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
        self.lbl_path.setStyleSheet("font-size: 13px;")
        self.lbl_path.setWordWrap(True)
        main_layout.addWidget(self.lbl_path)

        # 3. 模式选择 (Radio Buttons)
        self.grp_mode = QGroupBox("第一步：选择处理模式")
        self.grp_mode.setFont(QFont("微软雅黑", 11, QFont.Weight.Bold))
        layout_mode = QHBoxLayout()

        self.rb_web = QRadioButton("网页手动模式 (推荐 DeepSeek  / ChatGPT)")
        self.rb_api = QRadioButton("API 自动模式 (需配置 Key)")
        self.rb_web.setFont(QFont("微软雅黑", 10))
        self.rb_api.setFont(QFont("微软雅黑", 10))
        self.rb_web.setChecked(True)  # 默认选中网页模式

        layout_mode.addWidget(self.rb_web)
        layout_mode.addWidget(self.rb_api)

        layout_mode.addStretch(1)

        # 主题切换
        lbl_theme = QLabel("主题:")
        lbl_theme.setFont(QFont("微软雅黑", 10))
        self.combo_theme = QComboBox()
        self.combo_theme.setFont(QFont("微软雅黑", 10))
        self.combo_theme.addItems(["浅色", "深色"])
        self.combo_theme.setFixedWidth(90)
        self.combo_theme.currentTextChanged.connect(self.on_theme_changed)
        layout_mode.addWidget(lbl_theme)
        layout_mode.addWidget(self.combo_theme)

        # API 配置按钮
        self.btn_api_config = QPushButton("⚙️ API 配置")
        self.btn_api_config.setFont(QFont("微软雅黑", 10))
        self.btn_api_config.setFixedWidth(120)
        self.btn_api_config.clicked.connect(self.open_api_config)
        self.btn_api_config.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; border-radius: 5px; padding: 5px; }"
            "QPushButton:hover { background-color: #F57C00; }"
        )

        # === 新增：教程按钮 ===
        self.btn_tutorial = QPushButton("📖 新手教程")
        self.btn_tutorial.setFont(QFont("微软雅黑", 10))
        self.btn_tutorial.setFixedWidth(120)
        self.btn_tutorial.setStyleSheet(
            "QPushButton { background-color: #673AB7; color: white; border-radius: 5px; padding: 5px; }"
            "QPushButton:hover { background-color: #5E35B1; }"
        )
        self.btn_tutorial.clicked.connect(self.start_tour)

        # 将两个按钮加入布局
        layout_mode.addWidget(self.btn_api_config)
        layout_mode.addWidget(self.btn_tutorial)

        self.grp_mode.setLayout(layout_mode)
        main_layout.addWidget(self.grp_mode)

        # 4. 组件选择 (Checkboxes)
        self.grp_comp = QGroupBox("第二步：选择组装内容")
        self.grp_comp.setFont(QFont("微软雅黑", 11, QFont.Weight.Bold))
        layout_comp = QVBoxLayout()

        # --- 4.1 预设单选按钮（使用 QButtonGroup 管理） ---
        preset_layout = QHBoxLayout()
        self.preset_group = QButtonGroup(self)

        self.rb_preset_thesis = QRadioButton("毕业论文")
        self.rb_preset_paper = QRadioButton("小论文")
        self.rb_preset_report = QRadioButton("实验报告")
        self.rb_preset_custom = QRadioButton("自定义")

        self._preset_map = {
            self.rb_preset_thesis: "thesis",
            self.rb_preset_paper: "paper",
            self.rb_preset_report: "report",
            self.rb_preset_custom: "custom",
        }

        for rb in [
            self.rb_preset_thesis,
            self.rb_preset_paper,
            self.rb_preset_report,
            self.rb_preset_custom,
        ]:
            rb.setFont(QFont("微软雅黑", 10))
            preset_layout.addWidget(rb)
            self.preset_group.addButton(rb)

        # 默认选中毕业论文
        self.rb_preset_thesis.setChecked(True)
        # 只在“被选中”时处理（避免一次切换触发两次）
        self.preset_group.buttonToggled.connect(self.on_preset_toggled)

        layout_comp.addLayout(preset_layout)

        # 分割线
        self.line_sep = QLabel()
        self.line_sep.setFixedHeight(1)
        layout_comp.addWidget(self.line_sep)

        # --- 4.2 具体组件复选框 ---
        self.checks = {}
        registry = build_engine.COMPONENT_REGISTRY

        # 定义显示顺序：cover_exp 紧挨 cover，整体 8 个一屏更紧凑
        display_order = [
            "cover",
            "cover_exp",
            "originality",
            "abs_cn",
            "abs_en",
            "symbols",
            "toc",
            "body",
        ]

        row_layout = QHBoxLayout()
        count = 0
        for key in display_order:
            if key not in registry:
                continue
            item = registry[key]
            cb = QCheckBox(item["desc"])
            cb.setFont(QFont("微软雅黑", 10))
            cb.stateChanged.connect(self.on_checkbox_changed)
            self.checks[key] = cb

            row_layout.addWidget(cb)
            count += 1

            # 每 4 个换一行
            if count % 4 == 0:
                layout_comp.addLayout(row_layout)
                row_layout = QHBoxLayout()

        if count % 4 != 0:
            layout_comp.addLayout(row_layout)

        self.grp_comp.setLayout(layout_comp)
        main_layout.addWidget(self.grp_comp)

        # 初始化复选框状态（应用默认预设）
        self.apply_preset("thesis")

        # 5. 导出设置
        grp_output = QGroupBox("第三步：导出设置")
        grp_output.setFont(QFont("微软雅黑", 11, QFont.Weight.Bold))
        layout_output = QVBoxLayout()

        # 5.1 导出位置（可任意目录；留空默认 outputs）
        row_dir = QHBoxLayout()
        lbl_dir = QLabel("导出目录(留空默认 outputs):")
        lbl_dir.setFont(QFont("微软雅黑", 10))
        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setFont(QFont("微软雅黑", 10))
        self.edit_output_dir.setPlaceholderText("留空则默认导出到项目的 outputs 文件夹")
        self.edit_output_dir.textChanged.connect(self.update_output_preview)

        self.btn_pick_output_dir = QPushButton("选择...")
        self.btn_pick_output_dir.setFont(QFont("微软雅黑", 10))
        self.btn_pick_output_dir.setFixedWidth(80)
        self.btn_pick_output_dir.clicked.connect(self.pick_output_dir)

        row_dir.addWidget(lbl_dir)
        row_dir.addWidget(self.edit_output_dir, 1)
        row_dir.addWidget(self.btn_pick_output_dir)
        layout_output.addLayout(row_dir)

        # 5.2 命名
        row_name = QHBoxLayout()
        lbl_name = QLabel("导出文件名:")
        lbl_name.setFont(QFont("微软雅黑", 10))
        self.edit_output_name = QLineEdit()
        self.edit_output_name.setFont(QFont("微软雅黑", 10))
        self.edit_output_name.setPlaceholderText("例如：我的论文")
        self.edit_output_name.textChanged.connect(self.update_output_preview)
        row_name.addWidget(lbl_name)
        row_name.addWidget(self.edit_output_name, 1)
        layout_output.addLayout(row_name)

        # 5.3 格式（可同时选择）
        row_fmt = QHBoxLayout()
        lbl_fmt = QLabel("导出格式:")
        lbl_fmt.setFont(QFont("微软雅黑", 10))
        self.cb_export_docx = QCheckBox("DOCX")
        self.cb_export_pdf = QCheckBox("PDF")
        self.cb_export_docx.setFont(QFont("微软雅黑", 10))
        self.cb_export_pdf.setFont(QFont("微软雅黑", 10))
        self.cb_export_docx.setChecked(True)
        self.cb_export_docx.stateChanged.connect(self.update_output_preview)
        self.cb_export_pdf.stateChanged.connect(self.update_output_preview)
        row_fmt.addWidget(lbl_fmt)
        row_fmt.addWidget(self.cb_export_docx)
        row_fmt.addWidget(self.cb_export_pdf)
        row_fmt.addStretch(1)
        layout_output.addLayout(row_fmt)

        # 5.4 预览
        self.lbl_output_preview = QLabel("")
        self.lbl_output_preview.setWordWrap(True)
        self.lbl_output_preview.setFont(QFont("Consolas", 9))
        layout_output.addWidget(self.lbl_output_preview)

        grp_output.setLayout(layout_output)
        main_layout.addWidget(grp_output)

        # 6. 开始按钮
        self.btn_start = QPushButton("开始排版")
        self.btn_start.setFixedHeight(50)
        self.btn_start.setFont(QFont("微软雅黑", 13, QFont.Weight.Bold))
        self.btn_start.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; border-radius: 8px; }"
            "QPushButton:hover { background-color: #1976D2; }"
            "QPushButton:disabled { background-color: #B0BEC5; }"
        )
        self.btn_start.clicked.connect(self.start_process)
        main_layout.addWidget(self.btn_start)

        # 7. 日志输出框
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("运行日志将显示在这里...")
        self.txt_log.setFont(QFont("Consolas", 10))
        # 样式由主题统一控制
        main_layout.addWidget(self.txt_log)

        # 初始化主题下拉框显示
        self.combo_theme.blockSignals(True)
        try:
            self.combo_theme.setCurrentText("深色" if self.current_theme == "dark" else "浅色")
        finally:
            self.combo_theme.blockSignals(False)

        # 初始化导出预览
        self.update_output_preview()

    # ================= 导出设置 =================

    def get_outputs_root(self) -> str:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(root_dir, "outputs")

    def sanitize_filename(self, name: str) -> str:
        invalid = '<>:/\\|?*"'
        cleaned = "".join(("_" if ch in invalid else ch) for ch in (name or ""))
        cleaned = cleaned.strip().strip(".")
        return cleaned

    def build_output_paths(self):
        outputs_root = self.get_outputs_root()
        name_widget = getattr(self, "edit_output_name", None)
        name_text = name_widget.text() if name_widget is not None else ""

        dir_widget = getattr(self, "edit_output_dir", None)
        dir_text = dir_widget.text() if dir_widget is not None else ""
        output_dir = (dir_text or "").strip()
        if not output_dir:
            output_dir = outputs_root
        # 允许输入相对路径：相对路径默认放到 outputs 下面
        if not os.path.isabs(output_dir):
            output_dir = os.path.abspath(os.path.join(outputs_root, output_dir))

        base = self.sanitize_filename((name_text or "").strip())

        if not base:
            if self.input_file:
                base = self.sanitize_filename(os.path.splitext(os.path.basename(self.input_file))[0])
            else:
                base = "Output"

        want_docx = bool(getattr(self, "cb_export_docx", None) and self.cb_export_docx.isChecked())
        want_pdf = bool(getattr(self, "cb_export_pdf", None) and self.cb_export_pdf.isChecked())

        docx_path = os.path.join(output_dir, f"{base}.docx") if want_docx else None
        pdf_path = os.path.join(output_dir, f"{base}.pdf") if want_pdf else None
        return outputs_root, output_dir, base, docx_path, pdf_path

    def update_output_preview(self):
        if not hasattr(self, "lbl_output_preview"):
            return
        _outputs_root, output_dir, _base, docx_path, pdf_path = self.build_output_paths()
        show_dir = output_dir

        lines = [f"输出目录: {show_dir}"]
        if docx_path:
            lines.append(f"- {docx_path}")
        if pdf_path:
            lines.append(f"- {pdf_path}")
        if not docx_path and not pdf_path:
            lines.append("(请至少选择一种导出格式)")

        self.lbl_output_preview.setText("\n".join(lines))

    def pick_output_dir(self):
        """选择导出目录；留空则默认 outputs。"""
        outputs_root = self.get_outputs_root()
        os.makedirs(outputs_root, exist_ok=True)

        current_dir = (getattr(self, "edit_output_dir", None).text() or "").strip() if hasattr(self, "edit_output_dir") else ""
        start_dir = current_dir if current_dir and os.path.isdir(current_dir) else outputs_root

        chosen = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            start_dir,
        )
        if not chosen:
            return

        self.edit_output_dir.setText(chosen)
        self.update_output_preview()

    # ================= 预设/复选框联动逻辑 =================

    def on_preset_toggled(self, button, checked):
        """预设改变 -> 更新复选框"""
        if not checked:
            return
        if self._suppress_preset_sync:
            return

        preset = self._preset_map.get(button)
        if not preset or preset == "custom":
            return

        self.apply_preset(preset)

    def apply_preset(self, preset_name):
        """应用预设：勾选对应组件"""
        target_keys = set(self.PRESETS.get(preset_name, []))
        for cb in self.checks.values():
            cb.blockSignals(True)
        try:
            for key, cb in self.checks.items():
                cb.setChecked(key in target_keys)
        finally:
            for cb in self.checks.values():
                cb.blockSignals(False)

    def on_checkbox_changed(self, _state):
        """复选框改变 -> 更新预设状态（匹配则切回预设，否则为自定义）"""
        current_selection = {k for k, cb in self.checks.items() if cb.isChecked()}

        matched = None
        if current_selection == set(self.PRESETS.get("thesis", [])):
            matched = self.rb_preset_thesis
        elif current_selection == set(self.PRESETS.get("paper", [])):
            matched = self.rb_preset_paper
        elif current_selection == set(self.PRESETS.get("report", [])):
            matched = self.rb_preset_report

        self._suppress_preset_sync = True
        try:
            if matched is not None:
                matched.setChecked(True)
            else:
                self.rb_preset_custom.setChecked(True)
        finally:
            self._suppress_preset_sync = False

    def open_api_config(self):
        """打开 API 配置对话框"""
        dialog = ApiConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.log("API 配置已更新")

    def start_tour(self):
        # 实例化引导引擎
        self.tour = OverlayTour(self)
        
        # 准备测试文件路径
        test_file_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "test", "你要排版的文件.txt"))
        
        def load_test_file():
            if os.path.exists(test_file_path):
                self.on_file_loaded(test_file_path)
            else:
                QMessageBox.warning(self, "提示", f"测试文件未找到: {test_file_path}")

        steps = [
            {
                "target": self.drop_area,
                "title": "第 1 步：导入文档",
                "text": "你可以将需要排版的 .docx 或 .txt 拖入这里。\n为了演示，点击【下一步】，我将为你自动加载测试文档。",
                "on_next": load_test_file
            },
            {
                "target": self.grp_mode,
                "title": "第 2 步：选择模式",
                "text": "我们推荐新手保持默认的【网页手动模式】，它可以免费使用各大 AI 的高级模型（如 DeepSeek R1），排版效果最好。"
            },
            {
                "target": self.grp_comp,
                "title": "第 3 步：选你所需",
                "text": "默认已经为你勾选了标准【毕业论文】需要的所有部件（封面、中英文摘要、目录、正文等）。你可以根据实际情况增减。"
            },
            {
                "target": self.btn_start,
                "title": "最后一步：一键生成",
                "text": "点击下方的【开始排版】按钮，程序会为你生成并复制专用提示词，随后弹窗会指导你去 AI 网页端进行交互。\n\n现在，就请您亲自点击这个真实按钮试试吧！"
            }
        ]
        
        self.tour.set_steps(steps)
        self.tour.start()

    def showEvent(self, event):
        super().showEvent(event)
        
        # 使用 QTimer.singleShot 延迟触发首次引导检查，确保主窗口完全渲染并接管事件循环
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.check_first_launch)

    def check_first_launch(self):
        if config_manager.is_first_launch():
            config_manager.set_first_launch(False)
            reply = QMessageBox.question(
                self,
                "欢迎使用",
                "检测到您是首次使用，是否开启实战新手引导（约需 2 分钟）？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.start_tour()

    # ================= 主题切换 =================

    def on_theme_changed(self, text: str):
        theme = "dark" if (text or "").strip() == "深色" else "light"
        self.apply_theme(theme)
        config_manager.set_theme(theme)

    def apply_theme(self, theme: str):
        theme = (theme or "light").lower()
        self.current_theme = theme

        # 应用全局样式（对话框也会继承）
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(global_stylesheet(theme))

        # 单独控制：日志框（原本固定为深色，这里做主题适配）
        if theme == "dark":
            self.txt_log.setStyleSheet(
                "QTextEdit { background-color: #0F1720; color: #80CBC4; border-radius: 6px; padding: 6px; border: 1px solid #263238; }"
            )
        else:
            self.txt_log.setStyleSheet(
                "QTextEdit { background-color: #FFFFFF; color: #1F2937; border-radius: 6px; padding: 6px; border: 1px solid #D0D0D0; }"
            )

        # 路径标签/分割线/拖拽区随主题刷新
        self.lbl_path.setStyleSheet(
            "font-size: 13px; color: #BDBDBD;" if theme == "dark" else "font-size: 13px; color: #666;"
        )
        if hasattr(self, "line_sep") and self.line_sep is not None:
            self.line_sep.setStyleSheet(
                "background-color: #2A2A2A;" if theme == "dark" else "background-color: #DDD;"
            )

        self.update_drop_area_style()

    def update_drop_area_style(self):
        """根据主题 + 是否已加载文件，刷新拖拽区样式。"""
        theme = self.current_theme
        loaded = bool(self.input_file)

        if loaded:
            # 已加载文件：保持绿色提示，但深色主题下略压暗
            if theme == "dark":
                self.drop_area.setStyleSheet(
                    "QLabel { border: 3px solid #4CAF50; border-radius: 15px; background-color: #0F2A18; color: #9FE6B3; }"
                )
            else:
                self.drop_area.setStyleSheet(
                    "QLabel { border: 3px solid #4CAF50; border-radius: 15px; background-color: #E8F5E9; color: #2E7D32; }"
                )
            return

        # 未加载文件：默认虚线拖拽提示
        if theme == "dark":
            self.drop_area.setStyleSheet(
                "QLabel { border: 3px dashed #555; border-radius: 15px; background-color: #1A1A1A; color: #BDBDBD; }"
                "QLabel:hover { border-color: #4CAF50; background-color: #0F2A18; color: #9FE6B3; }"
            )
        else:
            self.drop_area.setStyleSheet(
                "QLabel { border: 3px dashed #AAA; border-radius: 15px; background-color: #F0F0F0; color: #555; }"
                "QLabel:hover { border-color: #4CAF50; background-color: #E8F5E9; color: #2E7D32; }"
            )

    def on_file_loaded(self, path):
        self.input_file = path
        self.lbl_path.setText(f"✅ 已加载: {path}")
        filename = os.path.basename(path)
        self.drop_area.setText(f"📄\n文件已就绪\n{filename}\n或拖入其他文档")
        self.update_drop_area_style()
        self.log(f"文件已加载: {path}")

        # 默认导出名 = 输入文件名（去扩展名）
        try:
            self.edit_output_name.setText(os.path.splitext(os.path.basename(path))[0])
        except Exception:
            pass
        self.update_output_preview()

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
            with open(filepath, "a"):
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

        # === 导出设置校验 ===
        _outputs_root, output_dir, base, docx_path, pdf_path = self.build_output_paths()
        if not docx_path and not pdf_path:
            QMessageBox.warning(self, "提示", "请至少选择一种导出格式（DOCX / PDF）！")
            return
        if not (base or "").strip():
            QMessageBox.warning(self, "提示", "导出文件名不能为空！")
            return

        # 目录可写性/可创建性检查
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "无法创建导出目录", f"导出目录不可用：\n{output_dir}\n\n原因：{e}")
            return

        # 输出占用检测（尽量提前给用户反馈）
        for target in [p for p in [docx_path, pdf_path] if p]:
            if self.is_file_locked(target):
                QMessageBox.critical(
                    self,
                    "无法写入输出文件",
                    f"检测到输出文件正在被使用：\n{target}\n\n"
                    "请先关闭 Word 或其他占用该文件的程序，然后再试。",
                )
                return

        # 锁定按钮
        self.btn_start.setEnabled(False)
        self.btn_start.setText("正在处理中...")
        self.txt_log.clear()

        mode = "api" if self.rb_api.isChecked() else "web"

        # 如果是 API 模式，检查配置
        api_config = None
        if mode == "api":
            raw_config = config_manager.load_api_config()
            api_config = config_manager.get_selected_provider_config(raw_config)

            if not api_config or not api_config.get("api_key"):
                QMessageBox.warning(self, "提示", "请先配置 API 信息！\n点击【⚙️ API 配置】按钮进行设置。")
                self.btn_start.setEnabled(True)
                self.btn_start.setText("开始排版")
                return

        # 启动线程
        self.worker = WorkerThread(
            self.input_file,
            mode,
            selected_keys,
            api_config,
            output_dir=output_dir,
            output_basename=base,
            export_docx=bool(docx_path),
            export_pdf=bool(pdf_path),
        )
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
            "Word 文档 (*.docx)",
        )
        self.worker.set_save_path(path)

    def on_finish(self, success):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("开始排版")
        if success:
            _outputs_root, output_dir, _base, docx_path, pdf_path = self.build_output_paths()
            show_dir = output_dir
            tips = ["文档生成成功！", f"输出目录：{show_dir}"]
            if docx_path:
                tips.append(f"- {os.path.basename(docx_path)}")
            if pdf_path:
                tips.append(f"- {os.path.basename(pdf_path)}")
            QMessageBox.information(self, "成功", "\n".join(tips))
        else:
            QMessageBox.warning(self, "失败", "排版过程中出现错误，请查看下方日志。")
