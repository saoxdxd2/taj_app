import logging
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QListWidget, QStackedWidget, QMessageBox,
                               QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
                               QLabel, QSizePolicy)
from PySide6.QtCore import Qt

from src.core.session import CurrentSession
from src.modules.authentication.services import AuthenticationService
from src.i18n import _, tr
from src.ui.layout import autosize_dialog, scaled, text_width

from src.ui.widgets.dashboard_widget import DashboardWidget
from src.ui.widgets.product_widget import ProductWidget
from src.ui.widgets.customer_widget import CustomerWidget
from src.ui.widgets.supplier_widget import SupplierWidget
from src.ui.widgets.purchase_widget import PurchaseWidget
from src.ui.widgets.finance_widget import FinanceWidget
from src.ui.widgets.sales_widget import SalesWidget
from src.ui.widgets.settings_widget import SettingsWidget
from src.ui.widgets.calendar_widget import CalendarWidget

logger = logging.getLogger(__name__)


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_(tr.auth.title))
        # A minimum width that grows with the DPI instead of a fixed one:
        # a hardcoded 380px is correct only on a 96 DPI screen with English
        # text, and clips the label once either of those changes.
        autosize_dialog(self, min_width=380)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 28, 28, 20)

        title = QLabel(
            "<h2 style='color:#1f3a5f;'>Taj ERP</h2>"
            f"<p style='color:#718096;'>{_(tr.auth.subtitle)}</p>"
        )
        title.setTextFormat(Qt.RichText)
        title.setWordWrap(True)
        layout.addWidget(title)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(_(tr.auth.username))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText(_(tr.auth.password))
        self.password_input.setEchoMode(QLineEdit.Password)

        form_layout.addRow(_(tr.auth.username), self.username_input)
        form_layout.addRow(_(tr.auth.password), self.password_input)
        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Ok).setText(_(tr.auth.sign_in))
        self.button_box.button(QDialogButtonBox.Cancel).setText(_(tr.common.cancel))
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
                QMessageBox.warning(self, _(tr.auth.title), _(tr.auth.failed))
        except Exception as e:
            QMessageBox.critical(
                self, _(tr.auth.title), _(tr.auth.error, error=str(e))
            )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Taj ERP")
        # A starting size, not a constraint: setMinimumSize below keeps the
        # window usable, and the layout handles the rest.
        self.resize(1280, 800)
        self.setMinimumSize(scaled(900), scaled(560))

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
        # The width follows the longest translated label. A fixed 220px
        # truncates French labels such as "Approvisionnements" and is
        # wrong again at a different font size.
        self.sidebar.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Expanding
        )

        nav_items = [
            "🏠  " + _(tr.nav.dashboard),
            "📅  " + _(tr.nav.calendar),
            "📦  " + _(tr.nav.inventory),
            "👥  " + _(tr.nav.crm),
            "🚚  " + _(tr.nav.suppliers),
            "🛒  " + _(tr.nav.purchasing),
            "💰  " + _(tr.nav.finance),
            "🧾  " + _(tr.nav.sales),
            "📊  " + _(tr.nav.analytics),
            "⚙️  " + _(tr.nav.settings),
        ]
        self.sidebar.addItems(nav_items)
        # Derived from real font metrics, so the longest label always fits.
        widest = max(
            (text_width(item, self.sidebar) for item in nav_items), default=0
        )
        self.sidebar.setMinimumWidth(widest + scaled(48))

        # Main content area
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(16, 16, 16, 16)

        # Initialize widgets
        self.dashboard_widget = DashboardWidget()
        self.calendar_widget = CalendarWidget()
        self.product_widget = ProductWidget()
        self.customer_widget = CustomerWidget()
        self.supplier_widget = SupplierWidget()
        self.purchase_widget = PurchaseWidget()
        self.finance_widget = FinanceWidget()
        self.sales_widget = SalesWidget()
        from src.ui.widgets.analytics_widget import AnalyticsWidget
        self.analytics_widget = AnalyticsWidget()
        self.settings_widget = SettingsWidget()

        self.stack.addWidget(self.dashboard_widget)
        self.stack.addWidget(self.calendar_widget)
        self.stack.addWidget(self.product_widget)
        self.stack.addWidget(self.customer_widget)
        self.stack.addWidget(self.supplier_widget)
        self.stack.addWidget(self.purchase_widget)
        self.stack.addWidget(self.finance_widget)
        self.stack.addWidget(self.sales_widget)
        self.stack.addWidget(self.analytics_widget)
        self.stack.addWidget(self.settings_widget)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack)

        self.sidebar.currentRowChanged.connect(self._on_nav_changed)
        self.sidebar.setCurrentRow(0)

        # Periodically pick up website price updates dropped in the
        # sync folder (every 5 minutes)
        from PySide6.QtCore import QTimer
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(5 * 60 * 1000)
        self._sync_timer.timeout.connect(self._process_pending_updates)
        self._sync_timer.start()

        # Context Label
        context = CurrentSession.get_context()
        self.statusBar().showMessage(f"Logged in as: {context.username} ({context.role})")

    def _process_pending_updates(self):
        """Applies website price updates without letting a malformed file
        kill the Qt event loop."""
        try:
            from src.modules.websync.services import WebsiteSyncService
            WebsiteSyncService.process_pending_updates()
        except Exception as exc:
            logger.error(f"Website price-update processing failed: {exc}")

    def _on_nav_changed(self, index: int):
        """Refresh the dashboard each time it is opened so reminders stay current."""
        widget = self.stack.widget(index)
        if widget is self.dashboard_widget:
            try:
                self.dashboard_widget.refresh()
            except Exception as exc:
                logger.error(f"Dashboard refresh failed: {exc}")
        self.stack.setCurrentIndex(index)
