"""
Authentication dialogs:
- FirstRunSetupDialog: Shown on first launch to force admin to set real credentials.
- ChangePasswordDialog: Available in Settings to change the current user's password.
- CreateUserDialog: Administrator creates a new user account with a role.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QLabel, QMessageBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import logging
import html

logger = logging.getLogger(__name__)


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
        self.password_input.setPlaceholderText(
            "8+ characters, with upper/lowercase and a digit"
        )
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
        from src.security.sanitizers import validate_password_strength

        if not text:
            self.hint_label.setText("")
            return
        try:
            validate_password_strength(text)
        except ValueError as e:
            self.hint_label.setText(str(e))
            self.hint_label.setStyleSheet("color: #dc3545; font-size: 11px;")
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

            username = AuthenticationService.complete_first_run_setup(
                new_username=username, new_password=password
            )

            QMessageBox.information(
                self, "Setup Complete",
                f"Account '{username}' created successfully.\n\n"
                "You will be signed in automatically."
            )
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save account: {str(e)}")


class ChangePasswordDialog(QDialog):
    """
    Allows the currently logged-in user to change their password from Settings.
    """

    def __init__(self, username, context=None, parent=None):
        super().__init__(parent)
        self.username = username
        self.context = context
        self.setWindowTitle("Change Password")
        self.setMinimumWidth(380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        info = QLabel(
            f"Changing password for: <b>{html.escape(str(self.username))}</b>"
        )
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
        self.new_input.setPlaceholderText(
            "8+ characters, with upper/lowercase and a digit"
        )
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
        from src.core.session import CurrentSession

        try:
            context = self.context or CurrentSession.get_context()
            AuthenticationService.change_password(
                context=context,
                username=self.username,
                new_password=new_pass,
                current_password=current,
            )
            QMessageBox.information(self, "Success", "Password changed successfully.")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to change password: {str(e)}")


class CreateUserDialog(QDialog):
    """
    Administrator creates a new user account (username, password, role).
    The account is persisted in the database immediately.
    """

    def __init__(self, context=None, parent=None):
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Add User")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g. yassine")
        form.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText(
            "8+ characters, with upper/lowercase and a digit"
        )
        form.addRow("Password:", self.password_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.setPlaceholderText("Repeat password")
        form.addRow("Confirm Password:", self.confirm_input)

        from PySide6.QtWidgets import QComboBox
        self.role_combo = QComboBox()

        from src.core.session import CurrentSession
        from src.database.session import SessionLocal
        from src.modules.authentication.services import AuthenticationService

        try:
            self.context = self.context or CurrentSession.get_context()
        except RuntimeError:
            self.context = None
        self._roles_error = None
        try:
            with SessionLocal() as session:
                roles = AuthenticationService.list_roles(
                    context=self.context, session=session
                )
        except Exception as e:
            roles = []
            self._roles_error = str(e)
            logger.warning(f"Could not load roles for the user dialog: {e}")

        for role_name in roles:
            self.role_combo.addItem(role_name)
        if not roles:
            self.role_combo.addItem("No assignable roles")
            self.role_combo.setEnabled(False)
        form.addRow("Role:", self.role_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Create User")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        role_name = self.role_combo.currentText()

        if not username:
            QMessageBox.warning(self, "Validation Error", "Username cannot be empty.")
            return
        if len(password) < 8:
            QMessageBox.warning(self, "Validation Error", "Password must be at least 8 characters.")
            return
        if password != confirm:
            QMessageBox.warning(self, "Validation Error", "Passwords do not match.")
            return
        if getattr(self, "_roles_error", None):
            QMessageBox.warning(self, "Cannot Create User", self._roles_error)
            return
        if not self.role_combo.isEnabled() or not role_name:
            QMessageBox.warning(self, "Validation Error", "No role is available to assign.")
            return

        try:
            from src.core.session import CurrentSession
            from src.modules.authentication.services import AuthenticationService
            from src.database.session import SessionLocal

            context = self.context or CurrentSession.get_context()
            with SessionLocal() as session:
                AuthenticationService.create_user(
                    context=context,
                    session=session,
                    username=username,
                    password=password,
                    role_name=role_name,
                )
                session.commit()
            QMessageBox.information(
                self, "User Created",
                f"User '{username}' ({role_name}) created successfully.\n"
                "They can now log in with these credentials."
            )
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create user: {str(e)}")

