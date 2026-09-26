"""
Application-wide visual theme.

A clean, professional light theme with a deep-blue sidebar, an amber
accent (froid/clim brand feel), generous padding and clear hover/focus
states. Applied once at startup via apply_theme(app).

Sizes are expressed as DPI-scaled padding rather than fixed heights, so
the interface keeps its proportions on a high-DPI screen and stays
readable once the labels are translated.
"""
from src.ui.layout import scaled

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

# Spacing scale, so padding stays visually consistent.
UNIT = scaled(4)

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
    padding-top: {scaled(12)}px;
}}
QListWidget#sidebar::item {{
    /* Vertical padding instead of a fixed height: the row grows with the
       font and never clips a long translated label. */
    padding: {scaled(11)}px {scaled(18)}px;
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

/* ---------- KPI cards ---------- */
QFrame#kpi_card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
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
    width: {scaled(10)}px;
}}
QScrollBar::handle:vertical {{
    background: #b9c4d4;
    border-radius: 5px;
    min-height: {scaled(30)}px;
}}
"""


def build_qss() -> str:
    """
    Builds the stylesheet for the current display.

    Called at startup rather than at import time, so DPI-scaled values
    match the screen the window is actually opened on.
    """
    return QSS


def apply_theme(app) -> None:
    """
    Applies the global stylesheet to the application.

    Built at call time (not import time) so the DPI scaling reflects the
    screen the application actually opened on.
    """
    app.setStyleSheet(build_qss())