from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QSplitter, QLabel)
from PySide6.QtCore import Qt

from src.core.session import CurrentSession
from src.modules.sales.services import SalesService
from src.ui.dialogs.sales_dialogs import NewInvoiceDialog, InvoiceAddItemDialog

class SalesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = CurrentSession.get_context()
        
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Buttons - Invoices
        btn_layout = QHBoxLayout()
        self.btn_new_draft = QPushButton("New Draft Invoice")
        self.btn_validate = QPushButton("Validate Invoice")
        self.btn_refresh = QPushButton("Refresh")

        btn_layout.addWidget(self.btn_new_draft)
        btn_layout.addWidget(self.btn_validate)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()

        # Splitter for Invoices and Items
        splitter = QSplitter(Qt.Vertical)

        # Top: Invoices Table
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("Invoices"))
        
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(5)
        self.invoice_table.setHorizontalHeaderLabels(["ID", "Invoice Number", "Customer ID", "State", "Total Amount"])
        self.invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.invoice_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.invoice_table.setSelectionMode(QTableWidget.SingleSelection)
        self.invoice_table.itemSelectionChanged.connect(self.on_invoice_selected)
        top_layout.addWidget(self.invoice_table)

        # Bottom: Items Table
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        item_btn_layout = QHBoxLayout()
        item_btn_layout.addWidget(QLabel("Invoice Items"))
        self.btn_add_item = QPushButton("Add Item")
        self.btn_add_item.setEnabled(False)
        item_btn_layout.addWidget(self.btn_add_item)
        item_btn_layout.addStretch()
        bottom_layout.addLayout(item_btn_layout)

        self.item_table = QTableWidget()
        self.item_table.setColumnCount(5)
        self.item_table.setHorizontalHeaderLabels(["Item ID", "Product ID", "Quantity", "Unit Price", "VAT (%)"])
        self.item_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.item_table.setSelectionBehavior(QTableWidget.SelectRows)
        bottom_layout.addWidget(self.item_table)

        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        layout.addLayout(btn_layout)
        layout.addWidget(splitter)

        # Connect signals
        self.btn_new_draft.clicked.connect(self.create_draft)
        self.btn_validate.clicked.connect(self.validate_invoice)
        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_add_item.clicked.connect(self.add_item)

    def load_data(self):
        self.invoice_table.setRowCount(0)
        self.item_table.setRowCount(0)
        
        try:
            invoices = SalesService.get_all_invoices(self.context)
            for row, invoice in enumerate(invoices):
                self.invoice_table.insertRow(row)
                self.invoice_table.setItem(row, 0, QTableWidgetItem(str(invoice.id)))
                self.invoice_table.setItem(row, 1, QTableWidgetItem(invoice.invoice_number))
                self.invoice_table.setItem(row, 2, QTableWidgetItem(str(invoice.customer_id)))
                self.invoice_table.setItem(row, 3, QTableWidgetItem(invoice.state.value))
                self.invoice_table.setItem(row, 4, QTableWidgetItem(str(invoice.total_amount)))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load invoices: {str(e)}")

    def on_invoice_selected(self):
        self.item_table.setRowCount(0)
        selected = self.invoice_table.selectedItems()
        if not selected:
            self.btn_add_item.setEnabled(False)
            return

        invoice_id = int(self.invoice_table.item(selected[0].row(), 0).text())
        state = self.invoice_table.item(selected[0].row(), 3).text()
        
        # Only allow adding items if state is Draft
        self.btn_add_item.setEnabled(state == "Draft")

        try:
            invoice = SalesService.get_invoice_with_items(self.context, invoice_id)
            if invoice and invoice.items:
                for row, item in enumerate(invoice.items):
                    self.item_table.insertRow(row)
                    self.item_table.setItem(row, 0, QTableWidgetItem(str(item.id)))
                    self.item_table.setItem(row, 1, QTableWidgetItem(str(item.product_id)))
                    self.item_table.setItem(row, 2, QTableWidgetItem(str(item.quantity)))
                    self.item_table.setItem(row, 3, QTableWidgetItem(str(item.unit_price)))
                    self.item_table.setItem(row, 4, QTableWidgetItem(str(item.vat_rate)))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load items: {str(e)}")

    def create_draft(self):
        dialog = NewInvoiceDialog(self.context, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                SalesService.create_invoice_draft(
                    self.context, 
                    invoice_number=data["invoice_number"], 
                    customer_id=data["customer_id"]
                )
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create draft: {str(e)}")

    def add_item(self):
        selected = self.invoice_table.selectedItems()
        if not selected:
            return
        
        invoice_id = int(self.invoice_table.item(selected[0].row(), 0).text())

        dialog = InvoiceAddItemDialog(self.context, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                SalesService.add_item_to_invoice(
                    self.context,
                    invoice_id=invoice_id,
                    product_id=data["product_id"],
                    quantity=data["quantity"],
                    unit_price=data["unit_price"],
                    vat_rate=data["vat_rate"]
                )
                self.load_data()
                
                # Reselect the invoice to show updated items
                for i in range(self.invoice_table.rowCount()):
                    if self.invoice_table.item(i, 0).text() == str(invoice_id):
                        self.invoice_table.selectRow(i)
                        break
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add item: {str(e)}")

    def validate_invoice(self):
        selected = self.invoice_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Selection Required", "Please select an invoice to validate.")
            return

        invoice_id = int(self.invoice_table.item(selected[0].row(), 0).text())
        state = self.invoice_table.item(selected[0].row(), 3).text()

        if state != "Draft":
            QMessageBox.warning(self, "Invalid State", "Only Draft invoices can be validated.")
            return

        reply = QMessageBox.question(self, "Confirm Validation", 
                                     "Are you sure you want to validate this invoice? This will decrease stock and generate incoming financial entries.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                success = SalesService.validate_invoice(self.context, invoice_id=invoice_id)
                if success:
                    QMessageBox.information(self, "Success", "Invoice validated successfully.")
                    self.load_data()
                else:
                    QMessageBox.warning(self, "Warning", "Invoice could not be validated (may be empty).")
            except Exception as e:
                # Wait, adjust_stock might raise ValueError("Insufficient stock")
                QMessageBox.critical(self, "Error", f"Failed to validate invoice: {str(e)}")
