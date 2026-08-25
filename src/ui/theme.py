"""
Application-wide visual theme.

A clean, professional light theme with a deep-blue sidebar, an amber
accent (froid/clim brand feel), generous padding and clear hover/focus
states. Applied once at startup via apply_theme(app).
"""
from pathlib import Path

ACCENT = "#e67e22"          # warm orange accent
SIDEBAR_BG = "#1f3a5f"      # deep blue
SIDEBAR_ACTIVE = "#2c5282"
BG = "#f4f6f9"
CARD = "#ffffff"
TEXT = "#2d3748"
MUTED = "#718096"
BORDER = "#d7dee8"
OK_GREEN = "#27ae60"
DANGER_RED = "#c0392b"

QSS = f"""
* {{
    font-family: "Segoe UI", "Tahoma", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow, QDialog {{
    background: {BG};
}}

/* ---------- Sidebar ---------- */
QListWidget#sidebar {{
    background: {SIDEBAR_BG};
    color: #dbe4f0;
    border: none;
    outline: none;
    font-size: 14px;
    padding-top: 12px;
}}
QListWidget#sidebar::item {{
    height: 44px;
    padding-left: 18px;
    border: none;
}}
QListWidget#sidebar::item:hover {{
    background: {SIDEBAR_ACTIVE};
    color: white;
}}
QListWidget#sidebar::item:selected {{
    background: {ACCENT};
    color: white;
    font-weight: bold;
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 16px;
}}
QPushButton:hover {{
    background: #edf2f7;
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background: #e2e8f0;
}}
QPushButton:disabled {{
    color: {MUTED};
    background: #eceff3;
    border-color: {BORDER};
}}

/* ---------- Tables ---------- */
QTableWidget, QTableView {{
    background: {CARD};
    alternate-background-color: #f8fafc;
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {SIDEBAR_ACTIVE};
    selection-color: white;
}}
QHeaderView::section {{
    background: {SIDEBAR_BG};
    color: white;
    padding: 6px;
    border: none;
    font-weight: bold;
}}

/* ---------- Inputs ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus {{
    border: 2px solid {ACCENT};
}}

/* ---------- Group boxes / labels ---------- */
QGroupBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {SIDEBAR_BG};
}}

QLabel {{
    background: transparent;
}}

/* ---------- Status bar & misc ---------- */
QStatusBar {{
    background: {SIDEBAR_BG};
    color: #dbe4f0;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background: {CARD};
}}
QTabBar::tab {{
    padding: 8px 18px;
    background: #e9edf3;
    border: 1px solid {BORDER};
    border-bottom: none;
}}
QTabBar::tab:selected {{
    background: {CARD};
    font-weight: bold;
    color: {ACCENT};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: #b9c4d4;
    border-radius: 5px;
    min-height: 30px;
}}
"""


def apply_theme(app) -> None:
    """Apply the global stylesheet to the application."""
    app.setStyleSheet(QSS)