"""
Authentication dialogs:
- FirstRunSetupDialog: Shown on first launch to force admin to set real credentials.
- ChangePasswordDialog: Available in Settings to change the current user's password.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QLabel, QMessageBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class FirstRunSetupDialog(QDialog):
    """
    Shown on first launch when the admin account still has the default password.
    Forces the user to set a secure username and password before using the app.
    Cannot be dismissed without completing the setup.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("First-Time Setup - TAJ FROID ERP")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowCloseButtonHint
            & ~Qt.WindowContextHelpButtonHint
        )
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QLabel("Welcome to TAJ FROID ERP")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        header.setFont(font)
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        warning = QLabel(
            "This is your first login.\n\n"
            "The default administrator password has not been changed.\n"
            "You must create a secure username and password before continuing.\n\n"
            "This step cannot be skipped."
        )
        warning.setWordWrap(True)
        warning.setAlignment(Qt.AlignCenter)
        warning.setStyleSheet(
            "background-color: #fff3cd; color: #664d03; "
            "border: 1px solid #ffecb5; border-radius: 6px; padding: 12px;"
        )
        layout.addWidget(warning)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g. administrator")
        self.username_input.setMaxLength(50)
        form.addRow("New Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Minimum 8 characters")
        form.addRow("New Password:", self.password_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.setPlaceholderText("Repeat password")
        form.addRow("Confirm Password:", self.confirm_input)

        layout.addLayout(form)

        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #888; font-size: 11px;")
        self.password_input.textChanged.connect(self._update_strength_hint)
        layout.addWidget(self.hint_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Create Account and Continue")
        buttons.accepted.connect(self._on_accept)
        layout.addWidget(buttons)

    def _update_strength_hint(self, text):
        if not text:
            self.hint_label.setText("")
        elif len(text) < 8:
            self.hint_label.setText("Too short - minimum 8 characters")
            self.hint_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        elif len(text) < 12:
            self.hint_label.setText("Acceptable - a longer password is more secure")
            self.hint_label.setStyleSheet("color: #fd7e14; font-size: 11px;")
        else:
            self.hint_label.setText("Strong password")
            self.hint_label.setStyleSheet("color: #198754; font-size: 11px;")

    def _on_accept(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        if not username:
            QMessageBox.warning(self, "Validation Error", "Username cannot be empty.")
            return
        if len(username) < 3:
            QMessageBox.warning(self, "Validation Error", "Username must be at least 3 characters.")
            return
        if len(password) < 8:
            QMessageBox.warning(self, "Validation Error", "Password must be at least 8 characters.")
            return
        if password != confirm:
            QMessageBox.warning(self, "Validation Error", "Passwords do not match.")
            self.confirm_input.clear()
            self.confirm_input.setFocus()
            return

        try:
            from src.modules.authentication.services import AuthenticationService
            from src.modules.authentication.models import User
            from src.database.session import SessionLocal

            with SessionLocal() as session:
                from src.modules.authentication.models import Role as _Role
                _admin_role = session.query(_Role).filter(_Role.name == "Administrator").first()
                admin = session.query(User).filter(User.role_id == _admin_role.id).first() if _admin_role else None
                if admin:
                    if username != admin.username:
                        existing = session.query(User).filter(User.username == username).first()
                        if existing and existing.id != admin.id:
                            QMessageBox.warning(self, "Validation Error", f"Username '{username}' is already taken.")
                            return
                        admin.username = username
                    admin.password_hash = AuthenticationService.hash_password(password)
                    session.commit()

            QMessageBox.information(
                self, "Setup Complete",
                f"Account '{username}' created successfully.\n\nPlease log in with your new credentials."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save account: {str(e)}")


class ChangePasswordDialog(QDialog):
    """
    Allows the currently logged-in user to change their password from Settings.
    """

    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.setWindowTitle("Change Password")
        self.setMinimumWidth(380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        info = QLabel(f"Changing password for: <b>{self.username}</b>")
        info.setTextFormat(Qt.RichText)
        layout.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        self.current_input = QLineEdit()
        self.current_input.setEchoMode(QLineEdit.Password)
        self.current_input.setPlaceholderText("Current password")
        form.addRow("Current Password:", self.current_input)

        self.new_input = QLineEdit()
        self.new_input.setEchoMode(QLineEdit.Password)
        self.new_input.setPlaceholderText("Minimum 8 characters")
        form.addRow("New Password:", self.new_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.setPlaceholderText("Repeat new password")
        form.addRow("Confirm Password:", self.confirm_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Change Password")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        current = self.current_input.text()
        new_pass = self.new_input.text()
        confirm = self.confirm_input.text()

        if not current:
            QMessageBox.warning(self, "Validation Error", "Please enter your current password.")
            return
        if len(new_pass) < 8:
            QMessageBox.warning(self, "Validation Error", "New password must be at least 8 characters.")
            return
        if new_pass != confirm:
            QMessageBox.warning(self, "Validation Error", "New passwords do not match.")
            self.confirm_input.clear()
            self.confirm_input.setFocus()
            return

        from src.modules.authentication.services import AuthenticationService

        user_ok = AuthenticationService.authenticate_user(username=self.username, password=current)
        if not user_ok:
            QMessageBox.warning(self, "Incorrect Password", "The current password you entered is incorrect.")
            self.current_input.clear()
            self.current_input.setFocus()
            return

        try:
            AuthenticationService.change_password(username=self.username, new_password=new_pass)
            QMessageBox.information(self, "Success", "Password changed successfully.")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to change password: {str(e)}")

