from datetime import datetime, timezone

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QPushButton,
                               QHeaderView, QMessageBox)
from PySide6.QtCore import Qt

from src.core.session import CurrentSession
from src.modules.inventory.services import InventoryService
from src.modules.finance.services import FinanceService
from src.modules.analytics.services import ForecastService


class DashboardWidget(QWidget):
    """
    Home screen: the two things the boss checks every morning —
    what stock is lacking, and which checks are coming due.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = CurrentSession.get_context()
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        today = datetime.now().strftime("%A %d %B %Y")
        title = QLabel(f"<h2 style='color:#1f3a5f;'>Dashboard</h2>"
                       f"<span style='color:#718096;'>{today}</span>")
        title.setTextFormat(Qt.RichText)
        layout.addWidget(title)

        # --- Low stock section ---
        low_stock_header = QHBoxLayout()
        low_stock_header.addWidget(QLabel("<b>Low Stock (at or below reorder threshold)</b>"))
        self.low_stock_count_label = QLabel("")
        low_stock_header.addWidget(self.low_stock_count_label)
        low_stock_header.addStretch()
        layout.addLayout(low_stock_header)

        self.stock_table = QTableWidget(0, 5)
        self.stock_table.setHorizontalHeaderLabels(
            ["SKU", "Product", "In Stock", "Threshold", "To Order"]
        )
        self.stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stock_table.verticalHeader().setVisible(False)
        self.stock_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.stock_table)

        # --- Checks due section ---
        checks_header = QHBoxLayout()
        checks_header.addWidget(QLabel("<b>Checks Due (next 7 days + overdue)</b>"))
        self.checks_count_label = QLabel("")
        checks_header.addWidget(self.checks_count_label)
        checks_header.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        checks_header.addWidget(refresh_btn)
        layout.addLayout(checks_header)

        self.checks_table = QTableWidget(0, 6)
        self.checks_table.setHorizontalHeaderLabels(
            ["Check #", "Direction", "Status", "Amount (DH)", "Due Date", "Party"]
        )
        self.checks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.checks_table.verticalHeader().setVisible(False)
        self.checks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.checks_table)

        # --- Reorder forecast section ---
        forecast_header = QHBoxLayout()
        forecast_header.addWidget(
            QLabel("<b>Reorder Suggestions (next 30 days, from sales velocity)</b>")
        )
        self.forecast_count_label = QLabel("")
        forecast_header.addWidget(self.forecast_count_label)
        forecast_header.addStretch()
        layout.addLayout(forecast_header)

        self.forecast_table = QTableWidget(0, 6)
        self.forecast_table.setHorizontalHeaderLabels(
            ["SKU", "Product", "In Stock", "Sold (90d)", "Need (30d)", "Suggested Order"]
        )
        self.forecast_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.forecast_table.verticalHeader().setVisible(False)
        self.forecast_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.forecast_table)

    def refresh(self):
        self._load_low_stock()
        self._load_checks_due()
        self._load_forecast()

    def _load_forecast(self):
        try:
            suggestions = ForecastService.get_reorder_suggestions(self.context)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load reorder forecast: {e}")
            return

        self.forecast_table.setRowCount(len(suggestions))
        for row, s in enumerate(suggestions):
            values = [
                s["sku"],
                s["name"],
                str(s["stock"]),
                str(s["sold_in_window"]),
                str(s["horizon_need"]),
                str(s["suggested_qty"]),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 5:
                    cell.setForeground(Qt.red)
                    font = cell.font()
                    font.setBold(True)
                    cell.setFont(font)
                self.forecast_table.setItem(row, col, cell)

        count = len(suggestions)
        self.forecast_count_label.setText(
            f"({count} product{'s' if count != 1 else ''})"
            if count else "(no restocking needed)"
        )

    def _load_low_stock(self):
        try:
            items = InventoryService.get_low_stock_products(self.context)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load low stock: {e}")
            return

        self.stock_table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                item["sku"],
                item["name"],
                str(item["quantity"]),
                str(item["min_quantity"]),
                str(item["shortfall"]),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 4:  # shortfall highlighted
                    cell.setForeground(Qt.red)
                self.stock_table.setItem(row, col, cell)

        count = len(items)
        self.low_stock_count_label.setText(
            f"({count} product{'s' if count != 1 else ''} to reorder)"
            if count else "(nothing to reorder)"
        )
        self.low_stock_count_label.setStyleSheet(
            "color: #c0392b; font-weight: bold;" if count else "color: #27ae60;"
        )

    def _load_checks_due(self):
        try:
            checks = FinanceService.get_checks_due_within(self.context, days=7)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load checks: {e}")
            return

        today = datetime.now(timezone.utc).date()
        self.checks_table.setRowCount(len(checks))
        for row, check in enumerate(checks):
            due_date = check.due_date.date() if check.due_date else None
            overdue = bool(due_date and due_date < today)
            direction = check.direction.value if hasattr(check.direction, "value") else str(check.direction)
            status = check.status.value if hasattr(check.status, "value") else str(check.status)
            values = [
                check.check_number,
                direction,
                status,
                f"{check.amount:,.2f}",
                due_date.isoformat() if due_date else "-",
                check.party_name,
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if overdue:
                    cell.setForeground(Qt.red)
                    cell.setToolTip("OVERDUE")
                self.checks_table.setItem(row, col, cell)

        count = len(checks)
        overdue_count = sum(
            1 for c in checks
            if c.due_date and c.due_date.date() < today
        )
        summary = f"({count} check{'s' if count != 1 else ''}"
        if overdue_count:
            summary += f", {overdue_count} OVERDUE"
        summary += ")" if count else ""
        self.checks_count_label.setText(summary or "(no checks due)")
        self.checks_count_label.setStyleSheet(
            "color: #c0392b; font-weight: bold;" if overdue_count else ""
        )