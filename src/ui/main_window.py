import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QListWidget, QStackedWidget, QMessageBox,
                               QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
                               QLabel)
from PySide6.QtCore import Qt

from src.core.session import CurrentSession
from src.modules.authentication.services import AuthenticationService

from src.ui.widgets.dashboard_widget import DashboardWidget
from src.ui.widgets.product_widget import ProductWidget
from src.ui.widgets.customer_widget import CustomerWidget
from src.ui.widgets.supplier_widget import SupplierWidget
from src.ui.widgets.purchase_widget import PurchaseWidget
from src.ui.widgets.finance_widget import FinanceWidget
from src.ui.widgets.sales_widget import SalesWidget
from src.ui.widgets.settings_widget import SettingsWidget

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Taj ERP - Login")
        self.setFixedWidth(380)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 28, 28, 20)

        title = QLabel("<h2 style='color:#1f3a5f;'>Taj ERP</h2>"
                       "<p style='color:#718096;'>Sign in to continue</p>")
        title.setTextFormat(Qt.RichText)
        layout.addWidget(title)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)

        form_layout.addRow("Username", self.username_input)
        form_layout.addRow("Password", self.password_input)
        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.attempt_login)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def attempt_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        try:
            success = AuthenticationService.login(username=username, password=password)
            if success:
                self.accept()
            else:
                QMessageBox.warning(self, "Login Failed", "Invalid username or password.")
        except Exception as e:
            QMessageBox.critical(self, "Login Error", f"An error occurred: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Taj ERP - Enterprise Dashboard")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 680)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar navigation
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)

        nav_items = [
            "🏠  Dashboard",
            "📦  Inventory",
            "👥  CRM",
            "🚚  Suppliers",
            "🛒  Purchasing",
            "💰  Finance",
            "🧾  Sales",
            "⚙️  Settings"
        ]
        self.sidebar.addItems(nav_items)

        # Main content area
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(16, 16, 16, 16)

        # Initialize widgets
        self.dashboard_widget = DashboardWidget()
        self.product_widget = ProductWidget()
        self.customer_widget = CustomerWidget()
        self.supplier_widget = SupplierWidget()
        self.purchase_widget = PurchaseWidget()
        self.finance_widget = FinanceWidget()
        self.sales_widget = SalesWidget()
        self.settings_widget = SettingsWidget()

        self.stack.addWidget(self.dashboard_widget)
        self.stack.addWidget(self.product_widget)
        self.stack.addWidget(self.customer_widget)
        self.stack.addWidget(self.supplier_widget)
        self.stack.addWidget(self.purchase_widget)
        self.stack.addWidget(self.finance_widget)
        self.stack.addWidget(self.sales_widget)
        self.stack.addWidget(self.settings_widget)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack)

        self.sidebar.currentRowChanged.connect(self._on_nav_changed)
        self.sidebar.setCurrentRow(0)

        # Periodically pick up website price updates dropped in the
        # sync folder (every 5 minutes)
        from PySide6.QtCore import QTimer
        from src.modules.websync.services import WebsiteSyncService
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(5 * 60 * 1000)
        self._sync_timer.timeout.connect(
            lambda: WebsiteSyncService.process_pending_updates()
        )
        self._sync_timer.start()

        # Context Label
        context = CurrentSession.get_context()
        self.statusBar().showMessage(f"Logged in as: {context.username} ({context.role})")

    def _on_nav_changed(self, index: int):
        """Refresh the dashboard each time it is opened so reminders stay current."""
        widget = self.stack.widget(index)
        if widget is self.dashboard_widget:
            self.dashboard_widget.refresh()
        self.stack.setCurrentIndex(index)