import csv
import os

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from src.core.pdf_engine import PDFEngine
from src.modules.whatsapp.services import WhatsAppService
from src.ui.layout import add_elided_columns, scaled


class StatementDialog(QDialog):
    """
    Customer/supplier account statement: debit, credit and running balance
    for a period, with CSV export and a printable PDF.

    `loader(date_from, date_to)` returns the dict built by
    CRMService.get_customer_statement or SupplierService.get_supplier_statement.
    One dialog serves both parties, so the ledger stays identical on screen
    and on paper.
    """

    COLUMNS = ["Date", "Reference", "Type", "Document", "Due Date",
               "Debit", "Credit", "Balance"]

    def __init__(self, loader, title: str = "Account Statement", parent=None):
        super().__init__(parent)
        self.loader = loader
        self._base_title = title
        self._statement = None
        self._rows = []
        self.setWindowTitle(title)
        self.setMinimumSize(scaled(900), scaled(560))
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
        self.from_input.setMinimumWidth(scaled(130))
        filters.addWidget(self.from_input)
        filters.addWidget(QLabel("To:"))
        self.to_input = QDateEdit(QDate.currentDate())
        self.to_input.setCalendarPopup(True)
        self.to_input.setDisplayFormat("dd/MM/yyyy")
        self.to_input.setMinimumWidth(scaled(130))
        filters.addWidget(self.to_input)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        filters.addWidget(self.btn_refresh)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self.export_csv)
        filters.addWidget(self.btn_export)

        self.btn_print = QPushButton("Print / PDF")
        self.btn_print.clicked.connect(self.print_pdf)
        if not PDFEngine.is_available():
            self.btn_print.setEnabled(False)
            self.btn_print.setToolTip("PDF generation requires 'reportlab'.")
        filters.addWidget(self.btn_print)

        self.btn_whatsapp = QPushButton("WhatsApp")
        self.btn_whatsapp.clicked.connect(self.send_whatsapp)
        filters.addWidget(self.btn_whatsapp)
        filters.addStretch()
        layout.addLayout(filters)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        add_elided_columns(self.table, stretch_column=3)
        layout.addWidget(self.table, 1)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

    @staticmethod
    def _money(value) -> str:
        return f"{value:,.2f}"

    @staticmethod
    def _date(value) -> str:
        return value.strftime("%d/%m/%Y") if value else ""

    def refresh(self):
        try:
            statement = self.loader(
                self.from_input.date().toPython(),
                self.to_input.date().toPython(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load statement:\n{exc}")
            return

        self._statement = statement
        self._rows = statement["rows"]

        party = statement["party"]
        self.setWindowTitle(f"{self._base_title} - {party['name']}")
        closing = statement["closing_balance"]
        if statement.get("kind") == "customer":
            closing_label = "Still due" if closing >= 0 else "Customer credit"
        else:
            closing_label = "Payable" if closing >= 0 else "Advance paid"
        self.summary.setText(
            f"<b>{party['name']}</b> &nbsp; Opening: "
            f"<b>{self._money(statement['opening_balance'])} DH</b> &nbsp; "
            f"{closing_label}: <b>{self._money(abs(closing))} DH</b>"
        )

        self.table.setRowCount(len(self._rows))
        for row, movement in enumerate(self._rows):
            values = [
                self._date(movement["date"]),
                movement["reference"],
                movement["type"],
                movement["document"],
                self._date(movement["due_date"]),
                self._money(movement["debit"]) if movement["debit"] else "",
                self._money(movement["credit"]) if movement["credit"] else "",
                self._money(movement["balance"]),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 5 and movement["debit"]:
                    item.setForeground(QColor("#c0392b"))
                elif column == 6 and movement["credit"]:
                    item.setForeground(QColor("#27ae60"))
                elif column == 7:
                    font = QFont(item.font())
                    font.setBold(True)
                    item.setFont(font)
                if column >= 5:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, item)

    def export_csv(self):
        if not self._rows:
            QMessageBox.information(self, "Export", "There is nothing to export.")
            return
        name = self._statement["party"]["name"] if self._statement else "statement"
        safe_name = "".join(c if c.isalnum() else "_" for c in name)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Statement", f"releve_{safe_name}.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            # utf-8-sig + ';' opens cleanly in French Excel.
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(self.COLUMNS)
                for movement in self._rows:
                    writer.writerow([
                        self._date(movement["date"]),
                        movement["reference"],
                        movement["type"],
                        movement["document"],
                        self._date(movement["due_date"]),
                        f"{movement['debit']:.2f}" if movement["debit"] else "",
                        f"{movement['credit']:.2f}" if movement["credit"] else "",
                        f"{movement['balance']:.2f}",
                    ])
            QMessageBox.information(self, "Export", f"Statement exported to:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def print_pdf(self):
        if self._statement is None:
            return
        try:
            filepath = PDFEngine.generate_statement_pdf(self._statement)
        except Exception as exc:
            QMessageBox.critical(self, "Print Failed", str(exc))
            return
        # Opening the PDF lets the user print it from their usual reader.
        if hasattr(os, "startfile"):
            os.startfile(filepath)
        QMessageBox.information(
            self, "Statement Exported", f"Statement saved to:\n{filepath}"
        )

    def send_whatsapp(self):
        if self._statement is None:
            return
        error = WhatsAppService.configuration_error()
        if error:
            QMessageBox.warning(self, "WhatsApp not configured", error)
            return

        from src.ui.dialogs.whatsapp_dialog import WhatsAppMessageDialog

        dialog = WhatsAppMessageDialog(
            to_phone=self._statement["party"].get("phone") or "",
            message=WhatsAppService.build_statement_message(self._statement),
            parent=self,
        )
        dialog.exec()
