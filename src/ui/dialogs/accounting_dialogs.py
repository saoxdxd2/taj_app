"""Dialogs for cash/bank accounts, transfers, ledgers and payment methods."""
from __future__ import annotations

import csv
from decimal import Decimal

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from src.modules.accounting.models import AccountType
from src.modules.accounting.services import AccountingService
from src.ui.dialogs.base_dialog import FormDialog
from src.ui.layout import add_elided_columns, size_table_height


def _currency_label(amount) -> str:
    return f"{amount:,.2f} DH"


class AccountDialog(FormDialog):
    """Create or edit a cash/bank account."""

    def __init__(self, context, account: dict | None = None, parent=None):
        self.context = context
        self.account = account
        super().__init__(
            title="Edit Account" if account else "New Account",
            subtitle="A cash drawer or a bank account used by the payment ledger.",
            min_width=460,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Caisse principale, Banque Populaire")
        form.addRow("Name *", self.name_input)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Cash", userData=AccountType.CASH)
        self.type_combo.addItem("Bank", userData=AccountType.BANK)
        form.addRow("Type *", self.type_combo)

        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("Rib / account number (optional)")
        form.addRow("Account Number", self.number_input)

        self.bank_input = QLineEdit()
        self.bank_input.setPlaceholderText("Bank name (optional)")
        form.addRow("Bank", self.bank_input)

        self.opening_input = QDoubleSpinBox()
        self.opening_input.setRange(-9_999_999.99, 9_999_999.99)
        self.opening_input.setDecimals(2)
        self.opening_input.setSuffix(" DH")
        self.opening_input.setAlignment(Qt.AlignRight)
        form.addRow("Opening Balance", self.opening_input)

        self._lock_opening = False
        if self.account:
            self.name_input.setText(self.account["name"])
            index = self.type_combo.findData(
                self.account["type"]
                if isinstance(self.account["type"], AccountType)
                else AccountType(self.account["type"])
            )
            self.type_combo.setCurrentIndex(max(0, index))
            self.number_input.setText(self.account.get("account_number", ""))
            self.bank_input.setText(self.account.get("bank", ""))
            self.opening_input.setValue(float(self.account.get("opening_balance", 0)))
            # The service also enforces this; disabling the field explains why.
            if self.account.get("has_movements"):
                self.opening_input.setEnabled(False)
                self.opening_input.setToolTip(
                    "The opening balance cannot change after the first movement."
                )

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            ok_text="Save Account",
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Account name is required.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "account_type": self.type_combo.currentData(),
            "opening_balance": Decimal(str(self.opening_input.value())),
            "account_number": self.number_input.text().strip() or None,
            "bank": self.bank_input.text().strip() or None,
        }


class TransactionDialog(FormDialog):
    """Record money in or out of one account."""

    def __init__(self, context, mode: str = "deposit", parent=None):
        self.context = context
        self.mode = mode
        title = "Deposit Money" if mode == "deposit" else "Withdraw Money"
        super().__init__(
            title=title,
            subtitle="Every movement is written to the account ledger.",
            min_width=500,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.account_combo = QComboBox()
        self.accounts = AccountingService.list_accounts(self.context)
        for account in self.accounts:
            self.account_combo.addItem(
                f"{account['name']}  ({_currency_label(account['balance'])})",
                userData=account["id"],
            )
        form.addRow("Account *", self.account_combo)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, 9_999_999.99)
        self.amount_input.setDecimals(2)
        self.amount_input.setSuffix(" DH")
        self.amount_input.setAlignment(Qt.AlignRight)
        form.addRow("Amount *", self.amount_input)

        self.method_combo = QComboBox()
        self.method_combo.addItem("— None —", userData=None)
        self.methods = AccountingService.list_methods(self.context)
        for method in self.methods:
            self.method_combo.addItem(method["name"], userData=method["id"])
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        form.addRow("Payment Method", self.method_combo)

        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("Check / transfer reference")
        form.addRow("Reference", self.reference_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("e.g. Vente comptoir, achat fournisseur")
        form.addRow("Description *", self.description_input)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Date *", self.date_input)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            ok_text="Save Movement",
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def _selected_method(self) -> dict | None:
        method_id = self.method_combo.currentData()
        return next((m for m in self.methods if m["id"] == method_id), None)

    def _on_method_changed(self):
        method = self._selected_method()
        if method is None:
            self.reference_input.setPlaceholderText("Check / transfer reference")
            return
        if method["requires_reference"]:
            self.reference_input.setPlaceholderText("Required for this method")
        else:
            self.reference_input.setPlaceholderText("Optional")
        target = (
            method["deposit_account_id"] if self.mode == "deposit"
            else method["withdrawal_account_id"]
        )
        if target:
            index = self.account_combo.findData(target)
            if index >= 0:
                self.account_combo.setCurrentIndex(index)

    def validate_and_accept(self):
        if self.account_combo.currentData() is None:
            QMessageBox.warning(self, "Validation Error", "Select an account first.")
            return
        if not self.description_input.text().strip():
            QMessageBox.warning(
                self, "Validation Error", "A description is required."
            )
            return
        method = self._selected_method()
        if (
            method is not None
            and method["requires_reference"]
            and not self.reference_input.text().strip()
        ):
            QMessageBox.warning(
                self, "Validation Error",
                f"'{method['name']}' requires a reference.",
            )
            return
        self.accept()

    def get_data(self) -> dict:
        method_id = self.method_combo.currentData()
        return {
            "account_id": self.account_combo.currentData(),
            "amount": Decimal(str(self.amount_input.value())),
            "description": self.description_input.text().strip(),
            "method_id": method_id,
            "reference": self.reference_input.text().strip() or None,
            "movement_date": self.date_input.date().toPython(),
        }


class TransferDialog(FormDialog):
    """Move money between two accounts in one atomic double entry."""

    def __init__(self, context, parent=None):
        self.context = context
        super().__init__(
            title="Transfer Funds",
            subtitle="Creates one outgoing and one incoming movement.",
            min_width=500,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.accounts = AccountingService.list_accounts(self.context)
        self.from_combo = QComboBox()
        self.to_combo = QComboBox()
        for account in self.accounts:
            label = f"{account['name']}  ({_currency_label(account['balance'])})"
            self.from_combo.addItem(label, userData=account["id"])
            self.to_combo.addItem(label, userData=account["id"])
        if self.to_combo.count() > 1:
            self.to_combo.setCurrentIndex(1)

        form.addRow("From Account *", self.from_combo)
        form.addRow("To Account *", self.to_combo)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, 9_999_999.99)
        self.amount_input.setDecimals(2)
        self.amount_input.setSuffix(" DH")
        self.amount_input.setAlignment(Qt.AlignRight)
        form.addRow("Amount *", self.amount_input)

        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("Reference (optional)")
        form.addRow("Reference", self.reference_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Reason / note (optional)")
        form.addRow("Description", self.description_input)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Date *", self.date_input)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            ok_text="Transfer",
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def validate_and_accept(self):
        if self.from_combo.currentData() == self.to_combo.currentData():
            QMessageBox.warning(
                self, "Validation Error",
                "Choose two different accounts for a transfer.",
            )
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "from_account_id": self.from_combo.currentData(),
            "to_account_id": self.to_combo.currentData(),
            "amount": Decimal(str(self.amount_input.value())),
            "description": self.description_input.text().strip() or None,
            "reference": self.reference_input.text().strip() or None,
            "movement_date": self.date_input.date().toPython(),
        }


class LedgerDialog(QDialog):
    """Full movement history for one account, with running balance."""

    def __init__(self, context, account_id: int, parent=None):
        super().__init__(parent)
        self.context = context
        self.account_id = account_id
        self.setWindowTitle("Account Ledger")
        self.setMinimumSize(820, 520)
        self._rows: list[dict] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("From:"))
        self.from_input = QDateEdit(QDate.currentDate().addMonths(-1))
        self.from_input.setCalendarPopup(True)
        self.from_input.setDisplayFormat("dd/MM/yyyy")
        filters.addWidget(self.from_input)
        filters.addWidget(QLabel("To:"))
        self.to_input = QDateEdit(QDate.currentDate())
        self.to_input.setCalendarPopup(True)
        self.to_input.setDisplayFormat("dd/MM/yyyy")
        filters.addWidget(self.to_input)
        self.btn_refresh = QDialogButtonBox(QDialogButtonBox.Ok)
        self.btn_refresh.button(QDialogButtonBox.Ok).setText("Refresh")
        self.btn_refresh.accepted.connect(self.refresh)
        filters.addWidget(self.btn_refresh)
        self.btn_export = QDialogButtonBox(QDialogButtonBox.Save)
        self.btn_export.button(QDialogButtonBox.Save).setText("Export CSV")
        self.btn_export.accepted.connect(self.export_csv)
        filters.addWidget(self.btn_export)
        filters.addStretch()
        layout.addLayout(filters)

        self.summary = QLabel("")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Type", "Reference", "Description", "In", "Out", "Balance"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        add_elided_columns(self.table, stretch_column=3)
        layout.addWidget(self.table, 1)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

    def refresh(self):
        try:
            ledger = AccountingService.get_ledger(
                self.context, account_id=self.account_id,
                date_from=self.from_input.date().toPython(),
                date_to=self.to_input.date().toPython(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load ledger:\n{exc}")
            return

        account = ledger["account"]
        self.setWindowTitle(f"Ledger - {account['name']}")
        self.summary.setText(
            f"<b>{account['name']}</b> &nbsp; Opening: "
            f"{_currency_label(account['opening_balance'])} &nbsp; Closing: "
            f"<b>{_currency_label(account['balance'])}</b>"
        )
        self._rows = ledger["rows"]
        self.table.setRowCount(len(self._rows))
        for row, movement in enumerate(self._rows):
            values = [
                movement["date"].strftime("%d/%m/%Y"),
                movement["type"].value,
                movement["reference"],
                movement["description"],
                _currency_label(movement["amount"])
                if movement["direction"].value == "In" else "",
                _currency_label(movement["amount"])
                if movement["direction"].value == "Out" else "",
                _currency_label(movement["balance"]),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def export_csv(self):
        if not self._rows:
            QMessageBox.information(self, "Export", "There is nothing to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Ledger", "ledger.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            # utf-8-sig + ';' makes the file open cleanly in French Excel.
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(
                    ["Date", "Type", "Reference", "Description", "In", "Out", "Balance"]
                )
                for row in self._rows:
                    writer.writerow([
                        row["date"].strftime("%d/%m/%Y"),
                        row["type"].value,
                        row["reference"],
                        row["description"],
                        f"{row['amount']:.2f}" if row["direction"].value == "In" else "",
                        f"{row['amount']:.2f}" if row["direction"].value == "Out" else "",
                        f"{row['balance']:.2f}",
                    ])
            QMessageBox.information(self, "Export", f"Ledger exported to:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))


class PaymentMethodDialog(FormDialog):
    """Create or edit a 'moyen de paiement'."""

    def __init__(self, context, method: dict | None = None, parent=None):
        self.context = context
        self.method = method
        super().__init__(
            title="Edit Payment Method" if method else "New Payment Method",
            subtitle="Used when recording money in or out of an account.",
            min_width=480,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Espèce, Chèque, TPE")
        form.addRow("Name *", self.name_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Optional description")
        form.addRow("Description", self.description_input)

        self.requires_ref = QCheckBox("A reference is required (check number, transfer ref...)")
        form.addRow("", self.requires_ref)

        self.accounts = AccountingService.list_accounts(
            self.context, include_inactive=True
        )
        self.deposit_combo = QComboBox()
        self.withdrawal_combo = QComboBox()
        for combo in (self.deposit_combo, self.withdrawal_combo):
            combo.addItem("— None —", userData=0)
            for account in self.accounts:
                combo.addItem(account["name"], userData=account["id"])
        form.addRow("Default Deposit Account", self.deposit_combo)
        form.addRow("Default Withdrawal Account", self.withdrawal_combo)

        self.order_input = QSpinBox()
        self.order_input.setRange(0, 999)
        form.addRow("Display Order", self.order_input)

        if self.method:
            self.name_input.setText(self.method["name"])
            self.description_input.setText(self.method.get("description", ""))
            self.requires_ref.setChecked(bool(self.method["requires_reference"]))
            self._select(self.deposit_combo, self.method.get("deposit_account_id"))
            self._select(self.withdrawal_combo, self.method.get("withdrawal_account_id"))
            self.order_input.setValue(int(self.method.get("sort_order", 0)))

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            ok_text="Save Method",
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    @staticmethod
    def _select(combo: QComboBox, account_id):
        index = combo.findData(account_id or 0)
        combo.setCurrentIndex(max(0, index))

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(
                self, "Validation Error", "Payment method name is required."
            )
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "description": self.description_input.text().strip() or None,
            "requires_reference": self.requires_ref.isChecked(),
            "deposit_account_id": self.deposit_combo.currentData() or None,
            "withdrawal_account_id": self.withdrawal_combo.currentData() or None,
            "sort_order": self.order_input.value(),
        }
