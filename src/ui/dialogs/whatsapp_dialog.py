from PySide6.QtWidgets import (
    QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QPlainTextEdit,
)

from src.modules.whatsapp.services import WhatsAppError, WhatsAppService
from src.ui.dialogs.base_dialog import FormDialog
from src.ui.layout import scaled


class WhatsAppMessageDialog(FormDialog):
    """Compose and send one WhatsApp message through the Cloud API."""

    def __init__(self, to_phone: str = "", message: str = "", parent=None):
        super().__init__(
            title="Send WhatsApp Message",
            subtitle="Sent through the Meta WhatsApp Cloud API.",
            min_width=520,
            parent=parent,
        )
        self.setup_ui(to_phone, message)

    def setup_ui(self, to_phone: str, message: str):
        form = QFormLayout()
        self.make_form(form)

        self.to_input = QLineEdit(to_phone or "")
        self.to_input.setPlaceholderText("+212 6 12 34 56 78")
        self.message_input = QPlainTextEdit(message or "")
        self.message_input.setMinimumHeight(scaled(180))

        form.addRow("To (phone) *", self.to_input)
        form.addRow("Message *", self.message_input)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Send"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.send)

    def send(self):
        if not self.to_input.text().strip():
            QMessageBox.warning(
                self, "Validation Error", "A recipient phone number is required."
            )
            return
        if not self.message_input.toPlainText().strip():
            QMessageBox.warning(self, "Validation Error", "The message cannot be empty.")
            return

        try:
            WhatsAppService.send_text(
                self.to_input.text(), self.message_input.toPlainText()
            )
        except WhatsAppError as exc:
            QMessageBox.critical(self, "WhatsApp", str(exc))
            return
        except ValueError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
            return

        QMessageBox.information(self, "WhatsApp", "Message sent.")
        self.accept()
