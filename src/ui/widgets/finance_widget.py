from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QPushButton,
                               QMessageBox, QGroupBox, QGridLayout,
                               QTabWidget)

from src.core.session import CurrentSession
from src.modules.accounting.services import AccountingService
from src.modules.finance.services import FinanceService
from src.modules.finance.models import CheckStatus
from src.security.permissions import AccessDenied, PermissionManager
from src.ui.dialogs.finance_dialogs import NewCheckDialog
from src.ui.dialogs.accounting_dialogs import (
    AccountDialog, LedgerDialog, PaymentMethodDialog, TransactionDialog,
    TransferDialog, _currency_label,
)
from src.ui.layout import add_elided_columns, size_table_height
from src.ui.widgets.reconciliation_widget import ReconciliationWidget

ID_ROLE = Qt.ItemDataRole.UserRole


def _enum_text(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


class FinanceWidget(QWidget):
    """
    Finance page with four tabs: overview (cash flow + debtors), checks,
    cash/bank accounts and configurable payment methods.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = CurrentSession.get_context()
        self._can_view_reports = False
        self._can_view_checks = False
        self._can_update_checks = False
        self._can_view_accounts = False
        self._can_manage_accounts = False
        self._can_view_methods = False
        self._can_manage_methods = False
        self._can_view_reconciliation = False
        self._methods_by_id = {}
        self.setup_ui()
        self._apply_permission_visibility()
        self.refresh()

    def _has_permission(self, permission: str) -> bool:
        try:
            PermissionManager.verify_permission(self.context, permission)
            return True
        except AccessDenied:
            return False

    def _apply_permission_visibility(self):
        """Hides sections the current role may not read.

        The service layer still enforces every permission; this only avoids
        showing empty/erroring panels to users who cannot use them.
        """
        self._can_view_reports = self._has_permission("Finance.Reports.View")
        self.cash_box.setVisible(self._can_view_reports)
        self.debtors_label.setVisible(self._can_view_reports)
        self.debtors_table.setVisible(self._can_view_reports)

        self._can_view_checks = self._has_permission("Finance.Checks.View")
        self._can_update_checks = (
            self._can_view_checks
            and self._has_permission("Finance.Checks.Update")
        )
        for widget in (
            self.checks_title, self.btn_new_check, self.btn_deposit,
            self.btn_clear, self.btn_bounce, self.btn_cancel,
            self.btn_refresh, self.checks_table,
        ):
            widget.setVisible(self._can_view_checks)
        self.btn_new_check.setEnabled(
            self._can_view_checks
            and self._has_permission("Finance.Checks.Create")
        )
        self._update_transition_buttons(None)

        self._can_view_accounts = self._has_permission("Accounting.Accounts.View")
        self._can_manage_accounts = (
            self._can_view_accounts
            and self._has_permission("Accounting.Accounts.Manage")
        )
        self._can_view_methods = self._has_permission("Accounting.Methods.View")
        self._can_manage_methods = (
            self._can_view_methods
            and self._has_permission("Accounting.Methods.Manage")
        )
        self._can_view_reconciliation = self._has_permission(
            "Accounting.Reconciliation.View"
        )

        self.btn_add_account.setEnabled(self._can_manage_accounts)
        self.btn_transfer.setEnabled(self._can_manage_accounts)
        self.btn_add_method.setEnabled(self._can_manage_methods)
        self._on_account_selected()
        self._on_method_selected()

        # A tab with no readable content is hidden entirely.
        for index, visible in (
            (0, self._can_view_reports),
            (1, self._can_view_checks),
            (2, self._can_view_accounts),
            (3, self._can_view_methods),
            (4, self._can_view_reconciliation),
        ):
            self.tabs.setTabVisible(index, visible)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("<h2>Finance</h2>")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_overview_tab(), "Overview")
        self.tabs.addTab(self._build_checks_tab(), "Checks")
        self.tabs.addTab(self._build_accounts_tab(), "Accounts")
        self.tabs.addTab(self._build_methods_tab(), "Payment Methods")
        self.reconciliation_widget = ReconciliationWidget()
        self.tabs.addTab(self.reconciliation_widget, "Reconciliation")

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_overview_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        cash_box = QGroupBox("Cash Flow - current month")
        self.cash_box = cash_box
        grid = QGridLayout(cash_box)
        self.inflow_label = QLabel("-")
        self.outflow_label = QLabel("-")
        self.net_label = QLabel("-")
        for row, (name, widget) in enumerate((
            ("Money in:", self.inflow_label),
            ("Money out:", self.outflow_label),
            ("Net:", self.net_label),
        )):
            grid.addWidget(QLabel(name), row, 0)
            grid.addWidget(widget, row, 1)
        grid.setColumnStretch(2, 1)
        layout.addWidget(cash_box)

        self.debtors_label = QLabel("<b>Client Debtors (outstanding balances)</b>")
        layout.addWidget(self.debtors_label)
        self.debtors_table = QTableWidget(0, 4)
        self.debtors_table.setHorizontalHeaderLabels(
            ["Client", "Invoiced", "Paid", "Outstanding"]
        )
        self.debtors_table.verticalHeader().setVisible(False)
        self.debtors_table.setEditTriggers(QTableWidget.NoEditTriggers)
        add_elided_columns(self.debtors_table, stretch_column=0)
        size_table_height(self.debtors_table, visible_rows=5)
        layout.addWidget(self.debtors_table)
        layout.addStretch()
        return page

    def _build_checks_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        checks_header = QHBoxLayout()
        self.checks_title = QLabel("<b>Checks</b>")
        checks_header.addWidget(self.checks_title)
        self.btn_new_check = QPushButton("New Check")
        self.btn_deposit = QPushButton("Deposit")
        self.btn_clear = QPushButton("Cleared")
        self.btn_bounce = QPushButton("Bounced")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_refresh = QPushButton("Refresh")
        for b in (self.btn_new_check, self.btn_deposit, self.btn_clear,
                  self.btn_bounce, self.btn_cancel, self.btn_refresh):
            checks_header.addWidget(b)
        checks_header.addStretch()
        layout.addLayout(checks_header)

        self.checks_table = QTableWidget(0, 7)
        self.checks_table.setHorizontalHeaderLabels(
            ["Check #", "Direction", "Status", "Amount (DH)", "Due Date", "Party", "Bank"]
        )
        self.checks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.checks_table.setSelectionMode(QTableWidget.SingleSelection)
        self.checks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.checks_table.selectionModel().selectionChanged.connect(self._on_check_selected)
        add_elided_columns(self.checks_table, stretch_column=1)
        layout.addWidget(self.checks_table)

        self.btn_new_check.clicked.connect(self.on_new_check)
        self.btn_deposit.clicked.connect(lambda: self._transition("Deposited"))
        self.btn_clear.clicked.connect(lambda: self._transition("Cleared"))
        self.btn_bounce.clicked.connect(lambda: self._transition("Bounced"))
        self.btn_cancel.clicked.connect(lambda: self._transition("Cancelled"))
        self.btn_refresh.clicked.connect(self.refresh)

        self._update_transition_buttons(None)
        return page

    def _build_accounts_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        header = QHBoxLayout()
        self.btn_add_account = QPushButton("Add Account")
        self.btn_edit_account = QPushButton("Edit")
        self.btn_account_deposit = QPushButton("Deposit")
        self.btn_account_withdraw = QPushButton("Withdraw")
        self.btn_transfer = QPushButton("Transfer")
        self.btn_ledger = QPushButton("Ledger")
        self.btn_toggle_account = QPushButton("Close")
        self.btn_refresh_accounts = QPushButton("Refresh")
        for b in (self.btn_add_account, self.btn_edit_account,
                  self.btn_account_deposit, self.btn_account_withdraw,
                  self.btn_transfer, self.btn_ledger,
                  self.btn_toggle_account, self.btn_refresh_accounts):
            header.addWidget(b)
        header.addStretch()
        layout.addLayout(header)

        self.accounts_table = QTableWidget(0, 6)
        self.accounts_table.setHorizontalHeaderLabels(
            ["Name", "Type", "Number", "Bank", "Balance (DH)", "Status"]
        )
        self.accounts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.accounts_table.setSelectionMode(QTableWidget.SingleSelection)
        self.accounts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.accounts_table.selectionModel().selectionChanged.connect(
            self._on_account_selected
        )
        add_elided_columns(self.accounts_table, stretch_column=0)
        size_table_height(self.accounts_table, visible_rows=8)
        layout.addWidget(self.accounts_table)
        layout.addStretch()

        self.btn_add_account.clicked.connect(self.on_new_account)
        self.btn_edit_account.clicked.connect(self.on_edit_account)
        self.btn_account_deposit.clicked.connect(lambda: self.on_movement("deposit"))
        self.btn_account_withdraw.clicked.connect(lambda: self.on_movement("withdraw"))
        self.btn_transfer.clicked.connect(self.on_transfer)
        self.btn_ledger.clicked.connect(self.on_ledger)
        self.btn_toggle_account.clicked.connect(self.on_toggle_account)
        self.btn_refresh_accounts.clicked.connect(self.refresh)
        return page

    def _build_methods_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        header = QHBoxLayout()
        self.btn_add_method = QPushButton("Add Method")
        self.btn_edit_method = QPushButton("Edit")
        self.btn_toggle_method = QPushButton("Deactivate")
        self.btn_refresh_methods = QPushButton("Refresh")
        for b in (self.btn_add_method, self.btn_edit_method,
                  self.btn_toggle_method, self.btn_refresh_methods):
            header.addWidget(b)
        header.addStretch()
        layout.addLayout(header)

        self.methods_table = QTableWidget(0, 6)
        self.methods_table.setHorizontalHeaderLabels(
            ["Name", "Description", "Requires Ref.", "Default Deposit",
             "Default Withdrawal", "Status"]
        )
        self.methods_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.methods_table.setSelectionMode(QTableWidget.SingleSelection)
        self.methods_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.methods_table.selectionModel().selectionChanged.connect(
            self._on_method_selected
        )
        add_elided_columns(self.methods_table, stretch_column=1)
        size_table_height(self.methods_table, visible_rows=8)
        layout.addWidget(self.methods_table)
        layout.addStretch()

        self.btn_add_method.clicked.connect(self.on_new_method)
        self.btn_edit_method.clicked.connect(self.on_edit_method)
        self.btn_toggle_method.clicked.connect(self.on_toggle_method)
        self.btn_refresh_methods.clicked.connect(self.refresh)
        return page

    # ------------------------------------------------------------------

    def refresh(self):
        if self._can_view_reports:
            self._load_cash_flow()
            self._load_debtors()
        if self._can_view_checks:
            self._load_checks()
        if self._can_view_accounts:
            self._load_accounts()
        if self._can_view_methods:
            self._load_methods()
        if self._can_view_reconciliation:
            self.reconciliation_widget.refresh()

    @staticmethod
    def _red():
        from PySide6.QtGui import QColor
        return QColor("#c0392b")

    def _load_cash_flow(self):
        try:
            flow = FinanceService.get_cash_flow(self.context)
        except AccessDenied:
            for label in (self.inflow_label, self.outflow_label, self.net_label):
                label.setText("—")
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load cash flow: {e}")
            return
        self.inflow_label.setText(f"{flow['inflow']:,.2f} DH")
        self.inflow_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        self.outflow_label.setText(f"{flow['outflow']:,.2f} DH")
        self.outflow_label.setStyleSheet("color: #c0392b; font-weight: bold;")
        net_color = "#27ae60" if flow["net"] >= 0 else "#c0392b"
        self.net_label.setText(f"{flow['net']:,.2f} DH")
        self.net_label.setStyleSheet(f"color: {net_color}; font-weight: bold;")

    def _load_debtors(self):
        try:
            debtors = FinanceService.get_debtors(self.context)
        except AccessDenied:
            self.debtors_table.setRowCount(0)
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load debtors: {e}")
            return

        self.debtors_table.setRowCount(len(debtors))
        for row, d in enumerate(debtors):
            values = [
                d["company_name"],
                f"{d['total_invoiced']:,.2f}",
                f"{d['total_paid']:,.2f}",
                f"{d['outstanding']:,.2f}",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if col == 3:
                    cell.setForeground(self._red())
                self.debtors_table.setItem(row, col, cell)

    def _load_checks(self):
        try:
            checks = FinanceService.get_all_checks(self.context)
        except AccessDenied:
            self.checks_table.setRowCount(0)
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load checks: {e}")
            return

        today = datetime.now(timezone.utc).date()
        self.checks_table.setRowCount(len(checks))
        for row, check in enumerate(checks):
            due = check.due_date.date() if check.due_date else None
            overdue = bool(due and due < today and check.status == CheckStatus.PENDING)
            values = [
                check.check_number,
                _enum_text(check.direction),
                _enum_text(check.status),
                f"{check.amount:,.2f}",
                due.isoformat() if due else "-",
                check.party_name,
                check.bank or "",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if overdue:
                    cell.setForeground(self._red())
                    cell.setToolTip("OVERDUE")
                self.checks_table.setItem(row, col, cell)
            self.checks_table.item(row, 0).setData(1000, check.id)  # stash id

    def _selected_check_id(self):
        selection = self.checks_table.selectionModel()
        if not selection or not selection.hasSelection():
            return None
        row = selection.selectedRows()[0].row()
        item = self.checks_table.item(row, 0)
        return item.data(1000) if item else None

    def _selected_check_status(self):
        selection = self.checks_table.selectionModel()
        if not selection or not selection.hasSelection():
            return None
        row = selection.selectedRows()[0].row()
        return self.checks_table.item(row, 2).text()

    def _on_check_selected(self):
        self._update_transition_buttons(self._selected_check_status())

    def _update_transition_buttons(self, status):
        """Enable only the legal transitions for the selected check's state."""
        allowed = {
            "Pending": {"Deposited", "Cleared", "Cancelled"},
            "Deposited": {"Cleared", "Bounced"},
            "Bounced": {"Deposited", "Cancelled"},
        }.get(status, set())
        if not self._can_update_checks:
            allowed = set()
        self.btn_deposit.setEnabled("Deposited" in allowed)
        self.btn_clear.setEnabled("Cleared" in allowed)
        self.btn_bounce.setEnabled("Bounced" in allowed)
        self.btn_cancel.setEnabled("Cancelled" in allowed)

    def on_new_check(self):
        dialog = NewCheckDialog(self.context, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                FinanceService.create_check(self.context, **data)
                self._load_checks()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create check: {e}")

    def _transition(self, new_status: str):
        check_id = self._selected_check_id()
        if not check_id:
            QMessageBox.warning(self, "Selection Required", "Please select a check.")
            return
        reply = QMessageBox.question(
            self, "Confirm",
            f"Move this check to '{new_status}'?"
            + (" Money will be recorded in the journal." if new_status == "Cleared" else ""),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            FinanceService.update_check_status(self.context, check_id=check_id, new_status=new_status)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update check: {e}")

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def _load_accounts(self):
        try:
            accounts = AccountingService.list_accounts(self.context)
        except AccessDenied:
            self.accounts_table.setRowCount(0)
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load accounts: {e}")
            return

        self.accounts_table.setRowCount(len(accounts))
        for row, account in enumerate(accounts):
            values = [
                account["name"],
                _enum_text(account["type"]),
                account["account_number"],
                account["bank"],
                _currency_label(account["balance"]),
                "Active" if account["is_active"] else "Closed",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if col == 4 and account["balance"] < 0:
                    cell.setForeground(self._red())
                self.accounts_table.setItem(row, col, cell)
            self.accounts_table.item(row, 0).setData(ID_ROLE, account["id"])
        self._on_account_selected()

    def _selected_account_id(self):
        selection = self.accounts_table.selectionModel()
        if not selection or not selection.hasSelection():
            return None
        row = selection.selectedRows()[0].row()
        item = self.accounts_table.item(row, 0)
        return item.data(ID_ROLE) if item else None

    def _on_account_selected(self):
        has_selection = self._selected_account_id() is not None
        manage = self._can_manage_accounts
        for button in (self.btn_edit_account, self.btn_account_deposit,
                       self.btn_account_withdraw, self.btn_toggle_account):
            button.setEnabled(has_selection and manage)
        self.btn_ledger.setEnabled(has_selection)
        if has_selection:
            selection = self.accounts_table.selectionModel().selectedRows()
            if selection:
                row = selection[0].row()
                status_item = self.accounts_table.item(row, 5)
                closed = status_item is not None and status_item.text() == "Closed"
                self.btn_toggle_account.setText("Reopen" if closed else "Close")

    def on_new_account(self):
        dialog = AccountDialog(self.context, parent=self)
        if not dialog.exec():
            return
        try:
            AccountingService.create_account(self.context, **dialog.get_data())
            self._load_accounts()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create account: {e}")

    def on_edit_account(self):
        account_id = self._selected_account_id()
        if not account_id:
            QMessageBox.warning(self, "Selection Required", "Select an account first.")
            return
        try:
            account = AccountingService.get_account(self.context, account_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load account: {e}")
            return
        dialog = AccountDialog(self.context, account=account, parent=self)
        if not dialog.exec():
            return
        try:
            AccountingService.update_account(
                self.context, account_id=account_id, **dialog.get_data()
            )
            self._load_accounts()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update account: {e}")

    def on_movement(self, mode: str):
        if mode == "withdraw" and not self._selected_account_id():
            QMessageBox.warning(self, "Selection Required", "Select an account first.")
            return
        dialog = TransactionDialog(self.context, mode=mode, parent=self)
        if mode == "withdraw" and dialog.accounts:
            index = dialog.account_combo.findData(self._selected_account_id())
            if index >= 0:
                dialog.account_combo.setCurrentIndex(index)
        if not dialog.exec():
            return
        data = dialog.get_data()
        try:
            if mode == "deposit":
                AccountingService.deposit(self.context, **data)
            else:
                AccountingService.withdraw(self.context, **data)
            self._load_accounts()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to record movement: {e}")

    def on_transfer(self):
        if not self._can_manage_accounts:
            return
        dialog = TransferDialog(self.context, parent=self)
        if not dialog.exec():
            return
        try:
            AccountingService.transfer_funds(self.context, **dialog.get_data())
            self._load_accounts()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to transfer funds: {e}")

    def on_ledger(self):
        account_id = self._selected_account_id()
        if not account_id:
            QMessageBox.warning(self, "Selection Required", "Select an account first.")
            return
        LedgerDialog(self.context, account_id=account_id, parent=self).exec()

    def on_toggle_account(self):
        account_id = self._selected_account_id()
        if not account_id:
            return
        try:
            account = AccountingService.get_account(self.context, account_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load account: {e}")
            return
        closing = account["is_active"]
        action = "Close" if closing else "Reopen"
        reply = QMessageBox.question(
            self, f"{action} Account",
            f"{action} account '{account['name']}'?"
            + (" The balance must be zero." if closing else ""),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            AccountingService.set_account_active(
                self.context, account_id=account_id, is_active=not closing
            )
            self._load_accounts()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update account: {e}")

    # ------------------------------------------------------------------
    # Payment methods
    # ------------------------------------------------------------------

    def _load_methods(self):
        try:
            methods = AccountingService.list_methods(
                self.context, include_inactive=True
            )
        except AccessDenied:
            self.methods_table.setRowCount(0)
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load payment methods: {e}")
            return

        self._methods_by_id = {method["id"]: method for method in methods}
        self.methods_table.setRowCount(len(methods))
        for row, method in enumerate(methods):
            values = [
                method["name"],
                method["description"],
                "Yes" if method["requires_reference"] else "No",
                method["deposit_account_name"],
                method["withdrawal_account_name"],
                "Active" if method["is_active"] else "Inactive",
            ]
            for col, value in enumerate(values):
                self.methods_table.setItem(row, col, QTableWidgetItem(str(value)))
            self.methods_table.item(row, 0).setData(ID_ROLE, method["id"])
        self._on_method_selected()

    def _selected_method_id(self):
        selection = self.methods_table.selectionModel()
        if not selection or not selection.hasSelection():
            return None
        row = selection.selectedRows()[0].row()
        item = self.methods_table.item(row, 0)
        return item.data(ID_ROLE) if item else None

    def _on_method_selected(self):
        method_id = self._selected_method_id()
        method = self._methods_by_id.get(method_id)
        self.btn_edit_method.setEnabled(bool(method) and self._can_manage_methods)
        self.btn_toggle_method.setEnabled(bool(method) and self._can_manage_methods)
        if method:
            self.btn_toggle_method.setText(
                "Deactivate" if method["is_active"] else "Activate"
            )

    def on_new_method(self):
        dialog = PaymentMethodDialog(self.context, parent=self)
        if not dialog.exec():
            return
        try:
            AccountingService.create_method(self.context, **dialog.get_data())
            self._load_methods()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create payment method: {e}")

    def on_edit_method(self):
        method = self._methods_by_id.get(self._selected_method_id())
        if not method:
            return
        dialog = PaymentMethodDialog(self.context, method=method, parent=self)
        if not dialog.exec():
            return
        try:
            AccountingService.update_method(
                self.context, method_id=method["id"], **dialog.get_data()
            )
            self._load_methods()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update payment method: {e}")

    def on_toggle_method(self):
        method = self._methods_by_id.get(self._selected_method_id())
        if not method:
            return
        new_state = not method["is_active"]
        try:
            AccountingService.set_method_active(
                self.context, method_id=method["id"], is_active=new_state
            )
            self._load_methods()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update payment method: {e}")
