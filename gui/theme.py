from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


STYLESHEET = """
QWidget {
    background-color: #151a21;
    color: #e8edf4;
    font-family: "Inter", "Noto Sans", sans-serif;
    font-size: 13px;
}

QMainWindow, QStatusBar {
    background-color: #151a21;
}

QLabel#brandMark {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #1d4ed8,
        stop: 1 #1e3a8a
    );
    border-radius: 10px;
    color: white;
    font-size: 24px;
    font-weight: 700;
}

QLabel#title {
    color: #f1f5f9;
    font-size: 22px;
    font-weight: 700;
}

QLabel#dialogTitle {
    color: #f1f5f9;
    font-size: 18px;
    font-weight: 700;
}

QLabel#subtitle, QLabel#connectionStatus,
QLabel#progressStage, QLabel#copyrightLabel {
    color: #94a3b5;
}

QLabel#copyrightLabel {
    font-size: 11px;
}

QLabel#connectionStatus[connected="true"] {
    color: #8fb7ff;
}

QLabel#activityIndicator {
    color: #315fb9;
    font-size: 15px;
}

QGroupBox {
    border: none;
    margin-top: 18px;
    padding-top: 8px;
    color: #c9d3df;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 0;
    padding: 0;
}

QRadioButton {
    min-height: 40px;
    padding: 0 14px;
    spacing: 9px;
    border: 1px solid #344152;
    border-radius: 8px;
    background-color: #1d242d;
    color: #cbd5e1;
}

QRadioButton:hover {
    border-color: #46566a;
    background-color: #222b36;
}

QRadioButton:checked {
    border-color: #315fb9;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #1c2940,
        stop: 1 #17243a
    );
    color: #eef5ff;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
}

QRadioButton::indicator:unchecked {
    border: 1px solid #617086;
    border-radius: 7px;
    background: #151b22;
}

QRadioButton::indicator:checked {
    border: 3px solid #1b2940;
    border-radius: 7px;
    background: #4f7ed8;
}

QLineEdit, QTextEdit {
    background-color: #0e141a;
    border: 1px solid #344152;
    border-radius: 8px;
    color: #d8e0ea;
    selection-background-color: #1e40af;
}

QTableWidget {
    background-color: #0e141a;
    alternate-background-color: #121a23;
    border: 1px solid #344152;
    border-radius: 8px;
    gridline-color: #26313e;
    color: #d8e0ea;
}

QHeaderView::section {
    background-color: #1d2631;
    color: #aebccd;
    padding: 9px;
    border: none;
    border-bottom: 1px solid #344152;
    font-weight: 600;
}

QLineEdit {
    min-height: 40px;
    padding: 0 12px;
}

QLineEdit:focus, QTextEdit:focus {
    border-color: #3d66b5;
}

QTextEdit {
    padding: 10px;
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 12px;
}

QPushButton {
    min-height: 40px;
    padding: 0 16px;
    border: 1px solid #3a4655;
    border-radius: 8px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #303b48,
        stop: 1 #252e39
    );
    color: #e8edf4;
}

QPushButton:hover {
    border-color: #536277;
    background-color: #354251;
}

QPushButton#smallButton {
    min-height: 30px;
    padding: 0 11px;
    font-size: 12px;
}

QPushButton#smallButton[connectionAction="connect"] {
    border-color: #527a69;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #29443a,
        stop: 1 #22362f
    );
    color: #b7dec9;
}

QPushButton#smallButton[connectionAction="connect"]:hover {
    border-color: #67937f;
    background-color: #315044;
}

QPushButton#smallButton[connectionAction="disconnect"] {
    border-color: #80565d;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #482d33,
        stop: 1 #39262b
    );
    color: #e1b9bf;
}

QPushButton#smallButton[connectionAction="disconnect"]:hover {
    border-color: #98666e;
    background-color: #55363d;
}

QPushButton#smallButton[connectionAction="busy"] {
    border-color: #405777;
    background-color: #263346;
    color: #91a9c8;
}


QPushButton#primaryButton {
    border-color: #204aaa;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #1d4ed8,
        stop: 1 #1e40af
    );
    color: white;
    font-weight: 700;
}

QPushButton#primaryButton:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #2459e5,
        stop: 1 #234bbf
    );
}

QPushButton:disabled {
    border-color: #303946;
    background-color: #252c35;
    color: #657181;
}

QCheckBox {
    color: #cbd5e1;
    spacing: 9px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #536175;
    border-radius: 4px;
    background: #111820;
}

QCheckBox::indicator:checked {
    border-color: #315fb9;
    background-color: #1d4ed8;
}

QProgressBar {
    min-height: 6px;
    max-height: 6px;
    border: none;
    border-radius: 3px;
    background-color: #2b3541;
    color: transparent;
}

QProgressBar::chunk {
    border-radius: 3px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #1e40af,
        stop: 1 #376dcc
    );
}

QStatusBar {
    border-top: 1px solid #252e39;
    color: #7f8b99;
    font-size: 11px;
}

QMessageBox QPushButton {
    min-width: 90px;
}
"""


def add_shadow(
    widget,
    blur_radius=24,
    y_offset=6,
    opacity=110,
):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(0, 0, 0, opacity))
    widget.setGraphicsEffect(effect)


def apply_widget_shadows(window):
    add_shadow(
        window.brand_mark,
        blur_radius=28,
        y_offset=7,
        opacity=125,
    )
    add_shadow(
        window.sync_button,
        blur_radius=30,
        y_offset=8,
        opacity=135,
    )
    add_shadow(
        window.log_view,
        blur_radius=26,
        y_offset=6,
        opacity=100,
    )
