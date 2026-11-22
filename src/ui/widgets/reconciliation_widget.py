"""Bank reconciliation tab: import statements, explain lines, match invoices."""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.core.session import CurrentSession
from src.modules.banking.parsing import (
    StatementParseError, file_hash, parse_statement_file,
)
from src.modules.banking.services import BankingService
from src.security.permissions import AccessDenied, PermissionManager
from src.ui.dialogs.reconciliation_dialogs import (
    CategorizeDialog, ImportStatementDialog, MatchDialog,
)
from src.ui.layout import add_elided_columns, show_table_rows

ID_ROLE = Qt.ItemDataRole.UserRole

_STATUS_COLORS = {
    "Pending": QColor("#d68910"),
    "Matched": QColor("#27ae60"),
    "Ignored": QColor("#7f8c8d"),
}


def _has_permission(context, permission: str) -> bool:
    if context is None:
        return False
    try:
        PermissionManager.verify_permission(context, permission)
        return True
    except AccessDenied:
        return False


def _money(value) -> str:
    return "-" if value is None else f"{value:,.2f}"


def _date(value) -> str:
    return value.strftime("%d/%m/%Y") if value else "-"


class ReconciliationWidget(QWidget):
    """Fifth Finance tab: the bank says what happened, the app says why."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = CurrentSession.get_context()
        self._can_view = _has_permission(
            self.context, BankingService.PERM_VIEW
        )
        self._can_manage = _has_permission(
            self.context, BankingService.PERM_MANAGE
        )
        self._statement = None
        self._lines: list[dict] = []
        self._loading = False
        if self._can_view:
            self.setup_ui()
            self.refresh()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def setup_ui(self):
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Bank Statements</b>"))
        self.account_filter = QComboBox()
        self.account_filter.addItem("All accounts", userData=None)
        self.account_filter.currentIndexChanged.connect(self._load_statements)
        header.addWidget(self.account_filter)
        header.addStretch()
        self.btn_import = QPushButton("Import Statement...")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_import.setEnabled(self._can_manage)
        self.btn_import.clicked.connect(self.on_import)
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_import)
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        self.statements_table = QTableWidget(0, 8)
        self.statements_table.setHorizontalHeaderLabels(
            ["Period", "File", "Account", "In (DH)", "Out (DH)",
             "Closing (DH)", "Pending", "Status"]
        )
        self.statements_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.statements_table.verticalHeader().setVisible(False)
        self.statements_table.setSelectionMode(QTableWidget.SingleSelection)
        self.statements_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.statements_table.selectionModel().selectionChanged.connect(
            self._on_statement_selected
        )
        add_elided_columns(self.statements_table, stretch_column=1)
        layout.addWidget(self.statements_table)

        self.summary_label = QLabel("Import a statement or select one above.")
        self.summary_label.setTextFormat(Qt.RichText)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        actions = QHBoxLayout()
        self.btn_match = QPushButton("Match...")
        self.btn_categorize = QPushButton("Categorize...")
        self.btn_ignore = QPushButton("Ignore")
        self.btn_close = QPushButton("Close Statement")
        self.btn_delete = QPushButton("Delete")
        self.btn_export = QPushButton("Export CSV")
        for button in (
            self.btn_match, self.btn_categorize, self.btn_ignore,
            self.btn_close, self.btn_delete, self.btn_export,
        ):
            button.setEnabled(False)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)

        self.btn_match.clicked.connect(self.on_match)
        self.btn_categorize.clicked.connect(self.on_categorize)
        self.btn_ignore.clicked.connect(self.on_toggle_ignore)
        self.btn_close.clicked.connect(self.on_toggle_closed)
        self.btn_delete.clicked.connect(self.on_delete)
        self.btn_export.clicked.connect(self.on_export)

        self.lines_table = QTableWidget(0, 7)
        self.lines_table.setHorizontalHeaderLabels(
            ["Date", "Label", "In (DH)", "Out (DH)", "Category", "Status", "Matched To"]
        )
        self.lines_table.verticalHeader().setVisible(False)
        self.lines_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lines_table.setSelectionMode(QTableWidget.SingleSelection)
        self.lines_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lines_table.selectionModel().selectionChanged.connect(
            self._update_actions
        )
        add_elided_columns(self.lines_table, stretch_column=1)
        layout.addWidget(self.lines_table, 1)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def refresh(self):
        if not self._can_view:
            return
        self._load_accounts()
        self._load_statements()

    def _load_accounts(self):
        current = self.account_filter.currentData()
        try:
            accounts = BankingService.list_accounts(context=self.context)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load accounts: {exc}")
            return
        self.account_filter.blockSignals(True)
        self.account_filter.clear()
        self.account_filter.addItem("All accounts", userData=None)
        for account in accounts:
            label = account["name"]
            if account["bank"]:
                label += f" ({account['bank']})"
            self.account_filter.addItem(label, userData=account["id"])
        index = self.account_filter.findData(current)
        self.account_filter.setCurrentIndex(index if index >= 0 else 0)
        self.account_filter.blockSignals(False)

    def _load_statements(self, select_id=None):
        if not self._can_view:
            return
        keep = select_id or self._selected_statement_id()
        try:
            statements = BankingService.list_statements(
                context=self.context, account_id=self.account_filter.currentData()
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load statements: {exc}")
            return

        self._loading = True
        self.statements_table.setRowCount(len(statements))
        for row, statement in enumerate(statements):
            period = "-"
            if statement["period_start"] or statement["period_end"]:
                period = (f"{_date(statement['period_start'])} - "
                          f"{_date(statement['period_end'])}")
            values = [
                period,
                statement["file_name"],
                statement["account_name"],
                _money(statement["total_credits"]),
                _money(statement["total_debits"]),
                _money(statement["computed_closing"]),
                str(statement["pending"]),
                statement["status"],
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if col == 7 and statement["is_reconciled"]:
                    cell.setForeground(QColor("#27ae60"))
                if col == 6 and statement["pending"]:
                    cell.setForeground(QColor("#d68910"))
                self.statements_table.setItem(row, col, cell)
            self.statements_table.item(row, 0).setData(ID_ROLE, statement["id"])

        show_table_rows(self.statements_table, len(statements), 6, exact=True)
        self._loading = False
        if keep is not None and self._select_statement_row(keep):
            self._on_statement_selected()
        elif not statements:
            self._clear_detail()
        else:
            self._on_statement_selected()

    def _select_statement_row(self, statement_id) -> bool:
        for row in range(self.statements_table.rowCount()):
            item = self.statements_table.item(row, 0)
            if item is not None and item.data(ID_ROLE) == statement_id:
                self.statements_table.blockSignals(True)
                self.statements_table.selectRow(row)
                self.statements_table.blockSignals(False)
                return True
        return False

    def _selected_statement_id(self):
        selection = self.statements_table.selectionModel()
        if not selection or not selection.hasSelection():
            return None
        row = selection.selectedRows()[0].row()
        item = self.statements_table.item(row, 0)
        return item.data(ID_ROLE) if item else None

    def _on_statement_selected(self):
        if self._loading:
            return
        statement_id = self._selected_statement_id()
        if statement_id is None:
            self._clear_detail()
            return
        try:
            detail = BankingService.get_statement(
                context=self.context, statement_id=statement_id
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load statement: {exc}")
            return
        self._statement = detail["statement"]
        self._lines = detail["transactions"]
        self._fill_summary()
        self._fill_lines()
        self._update_actions()

    def _clear_detail(self):
        self._statement = None
        self._lines = []
        self.lines_table.setRowCount(0)
        self.summary_label.setText("Select a statement to see its bank lines.")
        self._update_actions()

    def _fill_summary(self):
        statement = self._statement
        if statement is None:
            return
        balance_ok = statement["is_balanced"]
        balance_text = (
            f"Balance verified ({_money(statement['computed_closing'])})."
            if balance_ok else
            "Balance does NOT match: opening + in - out = "
            f"{_money(statement['computed_closing'])} but the bank prints "
            f"{_money(statement['closing_balance'])}."
        )
        balance_color = "#27ae60" if balance_ok else "#c0392b"
        status = statement["status"]
        status_color = "#27ae60" if statement["is_reconciled"] else "#d68910"
        self.summary_label.setText(
            f"<b>{statement['file_name']}</b> &nbsp; {statement['account_name']}"
            f" &nbsp;&middot;&nbsp; {_date(statement['period_start'])} - "
            f"{_date(statement['period_end'])}<br>"
            f"Opening {_money(statement['opening_balance'])} &nbsp; "
            f"In {_money(statement['total_credits'])} &nbsp; "
            f"Out {_money(statement['total_debits'])} &nbsp; "
            f"Closing {_money(statement['computed_closing'])}<br>"
            f"Status <b style='color:{status_color};'>{status}</b> &nbsp; "
            f"Pending <b>{statement['pending']}</b> &nbsp; "
            f"Matched <b>{statement['matched']}</b> &nbsp; "
            f"Ignored <b>{statement['ignored']}</b> &nbsp;&middot;&nbsp; "
            f"<span style='color:{balance_color}; font-weight:bold;'>"
            f"{balance_text}</span>"
        )

    def _fill_lines(self):
        self.lines_table.setRowCount(len(self._lines))
        for row, line in enumerate(self._lines):
            matched = ", ".join(
                f"{allocation['document_type']} {allocation['document_number'] or ''}".strip()
                for allocation in line["allocations"]
            )
            values = [
                _date(line["date"]),
                line["label"],
                f"{line['credit']:,.2f}" if line["credit"] is not None else "",
                f"{line['debit']:,.2f}" if line["debit"] is not None else "",
                line["category"],
                line["status"],
                matched,
            ]
            color = _STATUS_COLORS.get(line["status"])
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if color is not None:
                    cell.setForeground(color)
                self.lines_table.setItem(row, col, cell)
            self.lines_table.item(row, 0).setData(ID_ROLE, line["id"])

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _selected_line(self):
        selection = self.lines_table.selectionModel()
        if not selection or not selection.hasSelection():
            return None
        row = selection.selectedRows()[0].row()
        if 0 <= row < len(self._lines):
            return self._lines[row]
        return None

    def _statement_is_open(self) -> bool:
        return bool(self._statement) and not self._statement["is_reconciled"]

    def _update_actions(self):
        line = self._selected_line()
        manage_open = self._can_manage and self._statement_is_open()
        self.btn_match.setEnabled(bool(manage_open and line and line["status"] == "Pending"))
        self.btn_categorize.setEnabled(bool(manage_open and line))
        self.btn_ignore.setEnabled(
            bool(manage_open and line and line["status"] != "Matched")
        )
        if line is not None:
            self.btn_ignore.setText(
                "Include" if line["status"] == "Ignored" else "Ignore"
            )
        else:
            self.btn_ignore.setText("Ignore")
        self.btn_close.setEnabled(bool(self._can_manage and self._statement))
        if self._statement and self._statement["is_reconciled"]:
            self.btn_close.setText("Reopen Statement")
        else:
            self.btn_close.setText("Close Statement")
        self.btn_delete.setEnabled(bool(manage_open))
        self.btn_export.setEnabled(bool(self._statement and self._lines))

    def _reload_detail(self):
        if self._statement is None:
            return
        statement_id = self._statement["id"]
        self._load_statements(select_id=statement_id)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def on_import(self):
        try:
            accounts = BankingService.list_accounts(context=self.context)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load accounts: {exc}")
            return
        if not accounts:
            QMessageBox.information(
                self, "No Bank Account",
                "Create the bank account of this statement first in the "
                "Accounts tab, then import the file here.",
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Bank Statement", "",
            "Bank statements (*.pdf *.csv);;All files (*)",
        )
        if not path:
            return
        try:
            parsed = parse_statement_file(Path(path))
        except StatementParseError as exc:
            QMessageBox.warning(self, "Cannot Read This File", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))
            return
        if not parsed.transactions:
            QMessageBox.warning(
                self, "Empty Statement", "No transaction lines were found."
            )
            return

        file_name = Path(path).name
        dialog = ImportStatementDialog(
            self.context, parsed, file_name, parent=self
        )
        if not dialog.exec():
            return
        data = dialog.get_data()
        try:
            result = BankingService.import_statement(
                context=self.context, account_id=data["account_id"],
                parsed=parsed, file_name=file_name,
                file_hash_value=file_hash(Path(path)),
                allow_unbalanced=data["allow_unbalanced"],
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))
            return
        QMessageBox.information(
            self, "Statement Imported",
            f"{result['transactions']} line(s) imported, "
            f"{result['already_explained']} already explained by the bank wording."
            + ("" if result["is_balanced"] else
               "\n\nWarning: the totals did not balance and stay flagged."),
        )
        self._load_statements(select_id=result["id"])

    def on_match(self):
        line = self._selected_line()
        if line is None:
            return
        try:
            suggestions = BankingService.suggestions(
                context=self.context, transaction_id=line["id"]
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to find matches: {exc}")
            return
        dialog = MatchDialog(self.context, line, suggestions, parent=self)
        if not dialog.exec():
            return
        try:
            result = BankingService.match(
                context=self.context, transaction_id=line["id"],
                allocations=dialog.get_allocations(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Match Failed", str(exc))
            return
        QMessageBox.information(
            self, "Line Matched",
            "Recorded against: " + ", ".join(result["documents"]),
        )
        self._reload_detail()

    def on_categorize(self):
        line = self._selected_line()
        if line is None:
            return
        dialog = CategorizeDialog(self.context, line, parent=self)
        if not dialog.exec():
            return
        try:
            BankingService.set_category(
                context=self.context, transaction_id=line["id"],
                **dialog.get_data(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._reload_detail()

    def on_toggle_ignore(self):
        line = self._selected_line()
        if line is None:
            return
        ignored = line["status"] != "Ignored"
        try:
            BankingService.ignore_transaction(
                context=self.context, transaction_id=line["id"], ignored=ignored
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._reload_detail()

    def on_toggle_closed(self):
        if self._statement is None:
            return
        reconciled = self._statement["is_reconciled"]
        action = "Reopen" if reconciled else "Close"
        detail = ""
        if not reconciled:
            detail = ("\n\nEvery line must be matched or explained, and the "
                      "totals must balance.")
        reply = QMessageBox.question(
            self, f"{action} Statement",
            f"{action} this statement?{detail}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            BankingService.reconcile_statement(
                context=self.context, statement_id=self._statement["id"],
                reconciled=not reconciled,
            )
        except Exception as exc:
            QMessageBox.critical(self, f"{action} Failed", str(exc))
            return
        self._reload_detail()

    def on_delete(self):
        if self._statement is None:
            return
        reply = QMessageBox.question(
            self, "Delete Statement",
            "Delete this imported statement and all its lines?\n"
            "Statements with matched invoices cannot be deleted.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            BankingService.delete_statement(
                context=self.context, statement_id=self._statement["id"]
            )
        except Exception as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))
            return
        self._clear_detail()
        self._load_statements()

    def on_export(self):
        if not self._lines or self._statement is None:
            return
        default_name = Path(self._statement["file_name"]).stem + "-lines.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Statement Lines", default_name, "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow([
                    "Date", "Label", "In", "Out", "Category", "Status",
                    "Matched To",
                ])
                for line in self._lines:
                    matched = ", ".join(
                        f"{a['document_type']} {a['document_number'] or ''}".strip()
                        for a in line["allocations"]
                    )
                    writer.writerow([
                        _date(line["date"]),
                        line["label"],
                        f"{line['credit']:.2f}" if line["credit"] is not None else "",
                        f"{line['debit']:.2f}" if line["debit"] is not None else "",
                        line["category"],
                        line["status"],
                        matched,
                    ])
            QMessageBox.information(self, "Export", f"Lines exported to:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
