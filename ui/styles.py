def global_stylesheet(theme: str) -> str:
    """全局主题样式（尽量不覆盖各控件的定制按钮色）。"""
    theme = (theme or "light").lower()
    if theme == "dark":
        return """
            QMainWindow, QDialog {
                background-color: #121212;
                color: #EAEAEA;
            }
            QWidget {
                background-color: #121212;
                color: #EAEAEA;
            }
            QGroupBox {
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background-color: #161616;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                color: #EAEAEA;
            }
            QLabel {
                color: #EAEAEA;
            }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #1E1E1E;
                color: #EAEAEA;
                border: 1px solid #303030;
                border-radius: 6px;
                padding: 6px;
                selection-background-color: #2D6CDF;
            }
            QComboBox::drop-down {
                border: none;
                width: 22px;
            }
            QPushButton {
                border: 1px solid #3A3A3A;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #1E1E1E;
                color: #EAEAEA;
            }
            QPushButton:hover {
                background-color: #262626;
            }
            QPushButton:disabled {
                color: #9A9A9A;
                background-color: #1A1A1A;
            }
            QRadioButton, QCheckBox {
                color: #EAEAEA;
            }

            /* Radio 选中态：绿色实心圆，便于识别 */
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 2px solid #777;
                background-color: transparent;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #4CAF50;
                background-color: #4CAF50;
            }
            QRadioButton::indicator:unchecked {
                border: 2px solid #777;
                background-color: transparent;
            }
        """

    # light
    return """
        QMainWindow, QDialog {
            background-color: #FAFAFA;
            color: #222;
        }
        QWidget {
            background-color: #FAFAFA;
            color: #222;
        }
        QGroupBox {
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            margin-top: 10px;
            padding: 10px;
            background-color: #FFFFFF;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 6px;
            color: #222;
        }
        QLabel {
            color: #222;
        }
        QLineEdit, QComboBox, QTextEdit {
            background-color: #FFFFFF;
            color: #222;
            border: 1px solid #D0D0D0;
            border-radius: 6px;
            padding: 6px;
            selection-background-color: #2D6CDF;
        }
        QComboBox::drop-down {
            border: none;
            width: 22px;
        }
        QPushButton {
            border: 1px solid #CFCFCF;
            border-radius: 6px;
            padding: 6px 10px;
            background-color: #FFFFFF;
            color: #222;
        }
        QPushButton:hover {
            background-color: #F3F3F3;
        }
        QPushButton:disabled {
            color: #9A9A9A;
            background-color: #EFEFEF;
        }
        QRadioButton, QCheckBox {
            color: #222;
        }

        /* Radio 选中态：绿色实心圆，便于识别 */
        QRadioButton::indicator {
            width: 14px;
            height: 14px;
            border-radius: 7px;
            border: 2px solid #999;
            background-color: transparent;
        }
        QRadioButton::indicator:checked {
            border: 2px solid #4CAF50;
            background-color: #4CAF50;
        }
        QRadioButton::indicator:unchecked {
            border: 2px solid #999;
            background-color: transparent;
        }
    """
