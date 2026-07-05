import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QListWidget, QStackedWidget, QMessageBox, 
                               QDialog, QFormLayout, QLineEdit, QDialogButtonBox)
from PySide6.QtCore import Qt

from src.core.session import CurrentSession
from src.modules.authentication.services import AuthenticationService

from src.ui.widgets.product_widget import ProductWidget
from src.ui.widgets.customer_widget import CustomerWidget
from src.ui.widgets.supplier_widget import SupplierWidget
from src.ui.widgets.purchase_widget import PurchaseWidget
from src.ui.widgets.sales_widget import SalesWidget

class LoginDialog(QDialog):
    def __init__(self, session_maker, parent=None):
        super().__init__(parent)
        self.session_maker = session_maker
        self.setWindowTitle("Taj ERP - Login")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
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

        with self.session_maker() as session:
            success = AuthenticationService.login(session, username, password)
            if success:
                self.accept()
            else:
                QMessageBox.warning(self, "Login Failed", "Invalid username or password.")


class MainWindow(QMainWindow):
    def __init__(self, session_maker):
        super().__init__()
        self.session_maker = session_maker
        self.setWindowTitle("Taj ERP - Enterprise Dashboard")
        self.resize(1024, 768)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)

        # Sidebar navigation
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        
        nav_items = [
            "Inventory",
            "CRM",
            "Suppliers",
            "Purchasing",
            "Sales"
        ]
        self.sidebar.addItems(nav_items)

        # Main content area
        self.stack = QStackedWidget()

        # Initialize widgets
        self.product_widget = ProductWidget(self.session_maker)
        self.customer_widget = CustomerWidget(self.session_maker)
        self.supplier_widget = SupplierWidget(self.session_maker)
        self.purchase_widget = PurchaseWidget(self.session_maker)
        self.sales_widget = SalesWidget(self.session_maker)

        self.stack.addWidget(self.product_widget)
        self.stack.addWidget(self.customer_widget)
        self.stack.addWidget(self.supplier_widget)
        self.stack.addWidget(self.purchase_widget)
        self.stack.addWidget(self.sales_widget)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        # Context Label
        context = CurrentSession.get_context()
        self.statusBar().showMessage(f"Logged in as: {context.username} ({context.role})")
