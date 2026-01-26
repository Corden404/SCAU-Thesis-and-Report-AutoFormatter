import os
from PyQt6.QtWidgets import QLabel, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont


class DropArea(QLabel):
    file_dropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setText("📂\n\n将论文文件拖拽至此\n(支持 .docx / .md / .txt)")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("微软雅黑", 13))
        # 默认样式（会被主窗口主题刷新覆盖）
        self.setStyleSheet(
            "QLabel { border: 3px dashed #aaa; border-radius: 15px; background-color: #f0f0f0; color: #555; }"
            "QLabel:hover { border-color: #4CAF50; background-color: #e8f5e9; color: #2E7D32; }"
        )
        self.setAcceptDrops(True)  # 开启拖拽支持

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
