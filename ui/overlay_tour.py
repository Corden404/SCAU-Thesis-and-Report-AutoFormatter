import os
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
)
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath

class OverlayTour(QWidget):
    finished = pyqtSignal()
    next_step_requested = pyqtSignal(int)
    
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        # 无边框，浮在顶层
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        # 背景透明
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.steps = []
        self.current_step_index = 0
        
        # 提示卡片
        self.card = QFrame(self)
        self.card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 8px;
                border: 1px solid #cccccc;
            }
        """)
        
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        self.lbl_title = QLabel()
        self.lbl_title.setFont(QFont("微软雅黑", 12, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #333333; border: none; background: transparent;")
        layout.addWidget(self.lbl_title)
        
        self.lbl_text = QLabel()
        self.lbl_text.setFont(QFont("微软雅黑", 10))
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet("color: #555555; border: none; background: transparent;")
        self.lbl_text.setMinimumWidth(300)
        self.lbl_text.setMaximumWidth(400)
        layout.addWidget(self.lbl_text)
        
        btn_layout = QHBoxLayout()
        self.btn_skip = QPushButton("跳过引导")
        self.btn_skip.setFont(QFont("微软雅黑", 10))
        self.btn_skip.setStyleSheet("QPushButton { color: #888; background: transparent; border: none; } QPushButton:hover { color: #555; }")
        self.btn_skip.clicked.connect(self.finish_tour)
        
        self.btn_next = QPushButton("下一步")
        self.btn_next.setFont(QFont("微软雅黑", 10))
        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btn_next.clicked.connect(self.next_step)
        
        btn_layout.addWidget(self.btn_skip)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_next)
        layout.addLayout(btn_layout)
        
        self.card.hide()
        
    def set_steps(self, steps):
        self.steps = steps
        
    def start(self):
        if not self.steps:
            return
        self.current_step_index = 0
        
        self.sync_geometry()
        self.parent_window.installEventFilter(self)
        self.show()
        self.update_step()
        
    def sync_geometry(self):
        if self.parent_window:
            rect = self.parent_window.geometry()
            self.setGeometry(rect)
            
    def eventFilter(self, obj, event):
        if obj == self.parent_window:
            if event.type() == event.Type.Resize or event.type() == event.Type.Move:
                self.sync_geometry()
                self.update_card_position()
        return super().eventFilter(obj, event)

    def update_step(self):
        if self.current_step_index >= len(self.steps):
            self.finish_tour()
            return
            
        step = self.steps[self.current_step_index]
        
        self.lbl_title.setText(step.get("title", ""))
        self.lbl_text.setText(step.get("text", ""))
        
        if self.current_step_index == len(self.steps) - 1:
            self.btn_next.setText("完成并开始排版")
            self.btn_next.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 4px;
                    padding: 6px 16px;
                }
                QPushButton:hover { background-color: #388E3C; }
            """)
        else:
            self.btn_next.setText("下一步")
            self.btn_next.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border-radius: 4px;
                    padding: 6px 16px;
                }
                QPushButton:hover { background-color: #1976D2; }
            """)
        
        self.card.adjustSize()
        self.update_card_position()
        self.card.show()
        
        self.update()

    def update_card_position(self):
        if self.current_step_index >= len(self.steps):
            return
            
        step = self.steps[self.current_step_index]
        target_widget = step.get("target")
        
        if target_widget and target_widget.isVisible():
            global_pos = target_widget.mapToGlobal(QPoint(0, 0))
            local_pos = self.mapFromGlobal(global_pos)
            target_rect = QRect(local_pos, target_widget.size())
            
            card_x = target_rect.center().x() - self.card.width() // 2
            card_y = target_rect.bottom() + 15
            
            if card_x < 10:
                card_x = 10
            elif card_x + self.card.width() > self.width() - 10:
                card_x = self.width() - self.card.width() - 10
                
            if card_y + self.card.height() > self.height() - 10:
                card_y = target_rect.top() - self.card.height() - 15
                
            self.card.move(card_x, card_y)
        else:
            self.card.move((self.width() - self.card.width()) // 2, (self.height() - self.card.height()) // 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        
        if self.current_step_index < len(self.steps):
            step = self.steps[self.current_step_index]
            target_widget = step.get("target")
            
            if target_widget and target_widget.isVisible():
                global_pos = target_widget.mapToGlobal(QPoint(0, 0))
                local_pos = self.mapFromGlobal(global_pos)
                target_rect = QRect(local_pos, target_widget.size())
                
                target_rect.adjust(-5, -5, 5, 5)
                
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.setBrush(Qt.GlobalColor.transparent)
                painter.setPen(Qt.PenStyle.NoPen)
                
                path = QPainterPath()
                from PyQt6.QtCore import QRectF
                path.addRoundedRect(QRectF(target_rect), 6.0, 6.0)
                painter.drawPath(path)
                
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.setPen(QColor(33, 150, 243))
                painter.drawPath(path)

    def mousePressEvent(self, event):
        # 拦截所有点击，除非点击在 card 上
        pass

    def next_step(self):
        step = self.steps[self.current_step_index]
        on_next = step.get("on_next")
        if on_next:
            on_next()
            
        self.next_step_requested.emit(self.current_step_index)
        
        # 针对最后一步的特殊处理（完成并开始）
        if self.current_step_index == len(self.steps) - 1:
            self.finish_tour()
            return
            
        self.current_step_index += 1
        self.update_step()

    def finish_tour(self):
        self.parent_window.removeEventFilter(self)
        self.hide()
        self.finished.emit()
        self.deleteLater()
