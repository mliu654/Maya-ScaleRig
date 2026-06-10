"""Visual styling for the PyQt6 UI."""

from __future__ import annotations

from pathlib import Path


CHEVRON_DOWN = (Path(__file__).resolve().parent / 'assets' / 'chevron_down.svg').as_posix()
CHECK_ICON = (Path(__file__).resolve().parent / 'assets' / 'check.svg').as_posix()

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
    padding: 8px;
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

QGroupBox QLabel {
    font-weight: 500;
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

QComboBox {
    padding: 4px 34px 4px 10px;
    min-height: 26px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    top: 1px;
    bottom: 1px;
    border-left: 1px solid #e1e7ef;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background: #f7fafc;
}

QComboBox::drop-down:hover {
    background: #eef6fa;
}

QComboBox::down-arrow {
    image: url("__CHEVRON_DOWN__");
    width: 12px;
    height: 12px;
    margin-right: 9px;
}

QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #cfd7e3;
    border-radius: 6px;
    padding: 4px;
    outline: 0;
    selection-background-color: #dcecf4;
    selection-color: #1f2a34;
}

QDoubleSpinBox {
    padding: 4px 12px;
    min-height: 26px;
    font-weight: 600;
    color: #1f3a4d;
    background: #fbfdff;
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
    spacing: 8px;
    font-weight: 500;
}

QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid #b7c2d0;
    background: #ffffff;
}

QCheckBox::indicator:checked {
    background: #247a9b;
    border-color: #247a9b;
    image: url("__CHECK_ICON__");
}

QFrame#optionControlsPanel {
    background: #fbfcfe;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
}

QFrame#optionTogglePanel {
    background: #f4f8fb;
    border: 1px solid #dce7ef;
    border-radius: 8px;
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
""".replace('__CHEVRON_DOWN__', CHEVRON_DOWN).replace('__CHECK_ICON__', CHECK_ICON)
