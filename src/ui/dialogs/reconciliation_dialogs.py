"""Dialogs for importing, categorizing and matching bank statement lines."""
from __future__ import annotations

import re
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QLabel, QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem,
)

from src.modules.banking.models import TransactionCategory
from src.modules.banking.services import (
    EXPLAINED_CATEGORIES, BankingService, builtin_category,
)
from src.ui.dialogs.base_dialog import FormDialog
from src.ui.layout import add_elided_columns, show_table_rows


def _currency(value) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f} DH"


def _short_date(value) -> str:
    return value.strftime("%d/%m/%Y") if value else "-"


class ImportStatementDialog(FormDialog):
    """Shows the parsed statement and picks the account before saving."""

    def __init__(self, context, parsed, file_name: str, parent=None):
        self.context = context
        self.parsed = parsed
        self.file_name = file_name
        super().__init__(
            title="Import Bank Statement",
            subtitle="Review what was read. Nothing is posted to accounting here.",
            min_width=880,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        parsed = self.parsed

        form = QFormLayout()
        self.make_form(form)

        info = QLabel(
            f"<b>{self.file_name}</b><br>"
            f"Period: {_short_date(parsed.period_start)} to "
            f"{_short_date(parsed.period_end)} &nbsp;&middot;&nbsp; "
            f"{len(parsed.transactions)} line(s)"
        )
        info.setTextFormat(Qt.RichText)
        form.addRow(info)

        self.account_combo = QComboBox()
        accounts = BankingService.list_accounts(context=self.context)
        for index, account in enumerate(accounts):
            label = account["name"]
            if account["bank"]:
                label += f" ({account['bank']})"
            self.account_combo.addItem(label, userData=account["id"])
            if self._same_account_number(
                account.get("account_number"), parsed.account_number
            ):
                self.account_combo.setCurrentIndex(index)
        form.addRow("Bank Account *", self.account_combo)

        totals = QLabel(
            f"Opening <b>{_currency(parsed.opening_balance)}</b> &nbsp; "
            f"Money in <b>{_currency(parsed.total_credits)}</b> &nbsp; "
            f"Money out <b>{_currency(parsed.total_debits)}</b> &nbsp; "
            f"Printed closing <b>{_currency(parsed.closing_balance)}</b>"
        )
        totals.setTextFormat(Qt.RichText)
        form.addRow("Totals", totals)

        if parsed.balanced:
            balance_text = (
                f"Verified: opening + money in - money out = "
                f"{_currency(parsed.computed_closing)}."
            )
            balance_style = "color: #27ae60; font-weight: bold;"
        else:
            reasons = " ".join(parsed.issues())
            balance_text = f"Does not balance. {reasons}"
            balance_style = "color: #c0392b; font-weight: bold;"
        self.balance_label = QLabel(balance_text)
        self.balance_label.setWordWrap(True)
        self.balance_label.setStyleSheet(balance_style)
        form.addRow("Check", self.balance_label)

        self.allow_unbalanced = QCheckBox(
            "Import anyway (the totals will stay flagged until corrected)"
        )
        self.allow_unbalanced.setEnabled(not parsed.balanced)
        form.addRow("", self.allow_unbalanced)

        self.preview = QTableWidget(0, 5)
        self.preview.setHorizontalHeaderLabels(
            ["Date", "Label", "In (DH)", "Out (DH)", "Likely category"]
        )
        self.preview.verticalHeader().setVisible(False)
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        add_elided_columns(self.preview, stretch_column=1)
        self._fill_preview()

        layout = self._root
        layout.addWidget(self.preview, 1)

        if not accounts:
            hint = QLabel(
                "No account exists yet. Create a bank account in the Accounts "
                "tab before importing a statement."
            )
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #c0392b;")
            layout.addWidget(hint)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            ok_text="Import Statement",
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)
        box.button(QDialogButtonBox.Save).setEnabled(bool(accounts))

    @staticmethod
    def _same_account_number(stored, printed) -> bool:
        """The PDF prints the RIB in groups, so compare only the digits."""
        if not stored or not printed:
            return False
        left = re.sub(r"\D", "", stored)
        right = re.sub(r"\D", "", printed)
        if not left or not right:
            return False
        return left in right or right in left

    def _fill_preview(self):
        transactions = self.parsed.transactions
        self.preview.setRowCount(len(transactions))
        for row, transaction in enumerate(transactions):
            category = builtin_category(
                transaction, f"{transaction.label} {transaction.details}"
            )
            values = [
                _short_date(transaction.operation_date),
                transaction.label,
                f"{transaction.credit:,.2f}" if transaction.credit is not None else "",
                f"{transaction.debit:,.2f}" if transaction.debit is not None else "",
                category.value,
            ]
            for col, value in enumerate(values):
                self.preview.setItem(row, col, QTableWidgetItem(str(value)))
        show_table_rows(self.preview, len(transactions), 8)
    def validate_and_accept(self):
        if self.account_combo.currentData() is None:
            QMessageBox.warning(
                self, "Account Required", "Select the bank account of this statement."
            )
            return
        if not self.parsed.balanced and not self.allow_unbalanced.isChecked():
            QMessageBox.warning(
                self, "Statement Does Not Balance",
                "The parsed lines do not add up to the printed balances. "
                "Tick 'Import anyway' if you have verified the file yourself.",
            )
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "account_id": self.account_combo.currentData(),
            "allow_unbalanced": self.allow_unbalanced.isChecked(),
        }


class CategorizeDialog(FormDialog):
    """Explain a bank line without changing the imported evidence."""

    def __init__(self, context, transaction: dict, parent=None):
        self.context = context
        self.transaction = transaction
        super().__init__(
            title="Categorize Bank Line",
            subtitle="The imported line stays as the bank wrote it.",
            min_width=520,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        summary = QLabel(
            f"<b>{_short_date(self.transaction['date'])}</b> &nbsp; "
            f"{'In' if self.transaction['direction'] == 'In' else 'Out'} "
            f"{_currency(self.transaction['amount'])}<br>"
            f"{self.transaction['label']}"
        )
        summary.setTextFormat(Qt.RichText)
        summary.setWordWrap(True)
        form.addRow(summary)

        self.category_combo = QComboBox()
        for category in TransactionCategory:
            self.category_combo.addItem(category.value, userData=category)
        form.addRow("Category *", self.category_combo)

        self.counterparty_input = QLineEdit(
            self.transaction.get("counterparty") or ""
        )
        self.counterparty_input.setPlaceholderText(
            "Who sent or received the money (optional)"
        )
        form.addRow("Counterparty", self.counterparty_input)

        self.exclude_check = QCheckBox("Excluded from reconciliation (already explained)")
        form.addRow("", self.exclude_check)

        current = TransactionCategory(self.transaction["category"])
        index = self.category_combo.findData(current)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        self.exclude_check.setChecked(
            self.transaction["status"] == "Ignored"
            or current in EXPLAINED_CATEGORIES
        )
        self.category_combo.currentIndexChanged.connect(self._sync_exclusion)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Apply"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def _sync_exclusion(self):
        category = self.category_combo.currentData()
        self.exclude_check.setChecked(category in EXPLAINED_CATEGORIES)

    def validate_and_accept(self):
        if self.category_combo.currentData() is None:
            QMessageBox.warning(self, "Category Required", "Select a category.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "category": self.category_combo.currentData(),
            "counterparty": self.counterparty_input.text().strip() or None,
            "ignore": self.exclude_check.isChecked(),
        }


class MatchDialog(FormDialog):
    """Pick the open invoices or purchases that this bank line settles."""

    def __init__(self, context, transaction: dict, suggestions: list, parent=None):
        self.context = context
        self.transaction = transaction
        self.suggestions = suggestions
        self._apply_boxes: list[QDoubleSpinBox | None] = []
        super().__init__(
            title="Match Bank Line",
            subtitle="The selected documents must add up to the bank amount.",
            min_width=860,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        transaction = self.transaction
        amount = Decimal(str(transaction["amount"]))
        self.amount = amount

        header = QLabel(
            f"<b>{_short_date(transaction['date'])}</b> &nbsp; "
            f"{'Money in' if transaction['direction'] == 'In' else 'Money out'} "
            f"<b>{_currency(amount)}</b><br>{transaction['label']}"
        )
        header.setTextFormat(Qt.RichText)
        header.setWordWrap(True)
        self._root.addWidget(header)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["", "Document", "Party", "Date", "Remaining (DH)", "Apply (DH)"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        add_elided_columns(self.table, stretch_column=2)
        self._root.addWidget(self.table, 1)

        self.total_label = QLabel("")
        self._root.addWidget(self.total_label)

        if not self.suggestions:
            note = QLabel(
                "No open document looks like this line. You can still "
                "categorize it, or ignore it if the bank already explained it."
            )
            note.setWordWrap(True)
            note.setStyleSheet("color: #7f8c8d;")
            self._root.addWidget(note)

        self._fill_table()

        box = self.add_buttons(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, ok_text="Match"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)
        box.button(QDialogButtonBox.Ok).setEnabled(bool(self.suggestions))

    def _fill_table(self):
        self.table.setRowCount(len(self.suggestions))
        for row, suggestion in enumerate(self.suggestions):
            is_batch = suggestion["kind"] == "batch"
            check = QTableWidgetItem("")
            check.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            check.setCheckState(Qt.CheckState.Unchecked)
            check.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, 0, check)

            document = suggestion["document_number"]
            if is_batch:
                document = f"Cheque batch: {document}"
            self.table.setItem(row, 1, QTableWidgetItem(str(document)))
            self.table.setItem(row, 2, QTableWidgetItem(str(suggestion["party"] or "")))
            self.table.setItem(
                row, 3, QTableWidgetItem(_short_date(suggestion["document_date"]))
            )
            self.table.setItem(
                row, 4, QTableWidgetItem(f"{suggestion['remaining']:,.2f}")
            )

            if is_batch:
                self.table.setItem(
                    row, 5, QTableWidgetItem(f"{suggestion['document_total']:,.2f}")
                )
                self._apply_boxes.append(None)
            else:
                spin = QDoubleSpinBox()
                spin.setRange(0.0, float(self.amount))
                spin.setDecimals(2)
                spin.setSuffix(" DH")
                spin.setAlignment(Qt.AlignRight)
                default = min(self.amount, Decimal(str(suggestion["remaining"])))
                spin.setValue(float(default))
                spin.valueChanged.connect(self._update_total)
                self.table.setCellWidget(row, 5, spin)
                self._apply_boxes.append(spin)

            if suggestion.get("reasons"):
                check.setToolTip("Matched because: " + ", ".join(suggestion["reasons"]))

        self.table.itemChanged.connect(self._on_item_changed)
        show_table_rows(self.table, len(self.suggestions), 7, exact=True)
        self._update_total()

    def _checked_rows(self) -> list[int]:
        rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                rows.append(row)
        return rows

    def _on_item_changed(self, item):
        if item.column() != 0:
            return
        if item.checkState() != Qt.CheckState.Checked:
            self._update_total()
            return
        batch_checked = self.suggestions[item.row()]["kind"] == "batch"
        for row in range(self.table.rowCount()):
            if row == item.row():
                continue
            other = self.table.item(row, 0)
            if other is None:
                continue
            if batch_checked or self.suggestions[row]["kind"] == "batch":
                self.table.blockSignals(True)
                other.setCheckState(Qt.CheckState.Unchecked)
                self.table.blockSignals(False)
        self._update_total()

    def _selected_total(self) -> Decimal:
        total = Decimal("0.00")
        for row in self._checked_rows():
            suggestion = self.suggestions[row]
            if suggestion["kind"] == "batch":
                total += sum(
                    (Decimal(str(a["amount"])) for a in suggestion["allocations"]),
                    Decimal("0.00"),
                )
            else:
                spin = self._apply_boxes[row]
                total += Decimal(str(spin.value() if spin else 0))
        return total.quantize(Decimal("0.01"))

    def _update_total(self):
        total = self._selected_total()
        if total == self.amount:
            style, verdict = "color: #27ae60; font-weight: bold;", "ready to match"
        elif total > self.amount:
            style, verdict = "color: #c0392b; font-weight: bold;", "too much"
        else:
            style, verdict = "color: #d68910; font-weight: bold;", "still missing"
        self.total_label.setText(
            f"Selected <b>{_currency(total)}</b> of {_currency(self.amount)} "
            f"&mdash; {verdict}"
        )
        self.total_label.setTextFormat(Qt.RichText)
        self.total_label.setStyleSheet(style)

    def validate_and_accept(self):
        rows = self._checked_rows()
        if not rows:
            QMessageBox.warning(
                self, "Selection Required",
                "Tick at least one document to match this line.",
            )
            return
        total = self._selected_total()
        if total != self.amount:
            QMessageBox.warning(
                self, "Amounts Do Not Match",
                f"The selected documents total {_currency(total)} but the bank "
                f"line is {_currency(self.amount)}.",
            )
            return
        self.accept()

    def get_allocations(self) -> list[dict]:
        allocations = []
        for row in self._checked_rows():
            suggestion = self.suggestions[row]
            if suggestion["kind"] == "batch":
                allocations.extend({
                    "invoice_id": allocation.get("invoice_id"),
                    "purchase_id": allocation.get("purchase_id"),
                    "amount": allocation["amount"],
                } for allocation in suggestion["allocations"])
                continue
            spin = self._apply_boxes[row]
            allocations.append({
                "invoice_id": suggestion.get("invoice_id"),
                "purchase_id": suggestion.get("purchase_id"),
                "amount": Decimal(str(spin.value() if spin else 0)),
            })
        return allocations
