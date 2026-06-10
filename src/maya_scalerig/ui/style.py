"""Visual styling for the PyQt6 UI."""

from __future__ import annotations


APP_STYLE = """
QWidget {
    background: #f6f7f9;
    color: #20242a;
    font-family: "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 10pt;
}

QMainWindow {
    background: #f6f7f9;
}

QGroupBox {
    background: #ffffff;
    border: 1px solid #d8dee7;
    border-radius: 8px;
    font-weight: 600;
    margin-top: 12px;
    padding: 14px 12px 12px 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #1d3f58;
}

QLabel {
    color: #425466;
    background: transparent;
}

QLineEdit,
QComboBox,
QDoubleSpinBox,
QTextEdit {
    background: #ffffff;
    border: 1px solid #cfd7e3;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: #2f80a7;
}

QLineEdit:focus,
QComboBox:focus,
QDoubleSpinBox:focus,
QTextEdit:focus {
    border: 1px solid #2f80a7;
}

QLineEdit:disabled,
QComboBox:disabled,
QDoubleSpinBox:disabled,
QTextEdit:disabled {
    background: #eef1f5;
    color: #7a8694;
}

QPushButton {
    background: #ffffff;
    border: 1px solid #c9d2df;
    border-radius: 6px;
    padding: 7px 14px;
    color: #263441;
    font-weight: 600;
}

QPushButton:hover {
    background: #eef6fa;
    border-color: #8cb8cd;
}

QPushButton:pressed {
    background: #dcecf4;
}

QPushButton:disabled {
    background: #edf0f4;
    border-color: #d8dde5;
    color: #9aa4b2;
}

QPushButton#primaryButton {
    background: #247a9b;
    border-color: #247a9b;
    color: #ffffff;
}

QPushButton#primaryButton:hover {
    background: #1f6f8d;
}

QPushButton#primaryButton:pressed {
    background: #195d76;
}

QPushButton#dangerButton {
    color: #a33c3c;
    border-color: #e0b7b7;
}

QPushButton#dangerButton:hover {
    background: #fff0f0;
    border-color: #cf8585;
}

QCheckBox {
    background: transparent;
    color: #304050;
    spacing: 7px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #b7c2d0;
    background: #ffffff;
}

QCheckBox::indicator:checked {
    background: #247a9b;
    border-color: #247a9b;
}

QTableWidget {
    background: #ffffff;
    alternate-background-color: #f7fafc;
    border: 1px solid #d8dee7;
    border-radius: 8px;
    gridline-color: #e7ebf0;
    selection-background-color: #dcecf4;
    selection-color: #1f2a34;
}

QHeaderView::section {
    background: #eef2f6;
    border: 0;
    border-bottom: 1px solid #d4dbe5;
    padding: 8px;
    color: #31465a;
    font-weight: 600;
}

QTableWidget::item {
    padding: 6px;
}

QProgressBar {
    background: #e8edf3;
    border: 1px solid #d4dbe5;
    border-radius: 6px;
    height: 16px;
    text-align: center;
    color: #263441;
}

QProgressBar::chunk {
    background: #36a37d;
    border-radius: 5px;
}

QTextEdit#logView {
    background: #101820;
    color: #dbe7ef;
    border: 1px solid #273341;
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 9.5pt;
}
"""
