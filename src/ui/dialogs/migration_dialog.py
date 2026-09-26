"""Recovery dialog shown when the database cannot be upgraded.

Offers the three real recovery paths: retry, restore the pre-migration
backup, or exit. There is deliberately no automatic rollback: a failed
upgrade can leave the schema half-applied, and a blind downgrade is a
worse outcome than a clear choice backed by a known-good backup.
"""
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QDialogButtonBox,
)
from PySide6.QtCore import Qt

from src.ui.dialogs.base_dialog import ACCENT, SIDEBAR_BG, MUTED


class MigrationErrorDialog(QDialog):
    """
    Usage:
        dialog = MigrationErrorDialog(error, backup_path)
        if dialog.exec() == MigrationErrorDialog.RESTORE:
            ...
    """

    RETRY = 1
    RESTORE = 2
    EXIT = 3

    def __init__(self, error: str, backup_path: str = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Upgrade Failed")
        self.setMinimumWidth(560)
        self.choice = self.EXIT

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(24, 20, 24, 18)

        header = QLabel(
            f"<h2 style='color:{SIDEBAR_BG};'>The database could not be upgraded</h2>"
            f"<span style='color:{MUTED};'>No further changes will be applied.</span>"
        )
        header.setTextFormat(Qt.RichText)
        root.addWidget(header)

        if backup_path:
            body = QLabel(
                "A backup was taken before the upgrade started, so your data can be "
                "restored to its previous state."
            )
            body.setWordWrap(True)
            root.addWidget(body)

            backup_label = QLabel(
                f"<code>{os.path.basename(backup_path)}</code>"
            )
            backup_label.setTextFormat(Qt.RichText)
            root.addWidget(backup_label)
        else:
            body = QLabel(
                "No pre-upgrade backup is available, so the previous state cannot be "
                "restored automatically."
            )
            body.setWordWrap(True)
            root.addWidget(body)

        details = QTextEdit()
        details.setReadOnly(True)
        details.setPlainText(error)
        details.setMaximumHeight(120)
        root.addWidget(details)

        buttons = QVBoxLayout()
        if backup_path:
            self.btn_restore = QPushButton("Restore Pre-Upgrade Backup and Restart")
            self.btn_restore.setStyleSheet(
                f"QPushButton {{ background:{ACCENT}; color:white; padding:8px; "
                "border-radius:4px; font-weight:bold; }"
                "QPushButton:hover { background:#d35400; }"
            )
            self.btn_restore.clicked.connect(self._choose_restore)
            buttons.addWidget(self.btn_restore)

        self.btn_retry = QPushButton("Retry Upgrade")
        self.btn_retry.clicked.connect(self._choose_retry)
        buttons.addWidget(self.btn_retry)

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(self._choose_exit)
        buttons.addWidget(box)
        root.addLayout(buttons)

    def _choose_retry(self):
        self.choice = self.RETRY
        self.accept()

    def _choose_restore(self):
        self.choice = self.RESTORE
        self.accept()

    def _choose_exit(self):
        self.choice = self.EXIT
        self.reject()
