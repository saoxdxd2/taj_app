"""
Shared base class for all form dialogs.

Gives every dialog a consistent look: comfortable margins, a branded
title header with an optional subtitle, a sensible minimum width, and
a Save/Cancel button row.
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
from PySide6.QtCore import Qt

ACCENT = "#e67e22"
SIDEBAR_BG = "#1f3a5f"
MUTED = "#718096"


class FormDialog(QDialog):
    """
    Usage:
        class MyDialog(FormDialog):
            def __init__(...):
                super().__init__(title="New Product",
                                 subtitle="Fields marked * are required")
                ... build self.form (QFormLayout) ...
                self.add_buttons(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    """

    def __init__(self, title: str, subtitle: str = "", min_width: int = 440,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)

        self._root = QVBoxLayout(self)
        self._root.setSpacing(14)
        self._root.setContentsMargins(24, 20, 24, 18)

        header = QLabel(f"<h2 style='color:{SIDEBAR_BG};'>{title}</h2>"
                        + (f"<span style='color:{MUTED};'>{subtitle}</span>" if subtitle else ""))
        header.setTextFormat(Qt.RichText)
        self._root.addWidget(header)

        # Subclasses add their form into this layout
        self.form = None  # set by subclass via make_form()

    def make_form(self, form_layout):
        """Registers the subclass's QFormLayout under the header."""
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)
        self._root.addLayout(form_layout)
        self.form = form_layout
        return form_layout

    def add_buttons(self, buttons: QDialogButtonBox.StandardButton,
                    ok_text: str = "Save") -> QDialogButtonBox:
        box = QDialogButtonBox(buttons)
        ok = box.button(QDialogButtonBox.Ok) or box.button(QDialogButtonBox.Save)
        if ok:
            ok.setText(ok_text)
            ok.setDefault(True)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        self._root.addWidget(box)
        return box