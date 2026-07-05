from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTableView, QHeaderView, QMessageBox, QSplitter, QLabel)
from PySide6.QtCore import Qt

from src.core.session import CurrentSession
from src.modules.sales.services import SalesService
from src.ui.dialogs.sales_dialogs import NewInvoiceDialog, InvoiceAddItemDialog
from src.ui.models.sales_model import InvoiceTableModel, InvoiceItemTableModel

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
        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_pdf = QPushButton("Export PDF")

        btn_layout.addWidget(self.btn_new_draft)
        btn_layout.addWidget(self.btn_validate)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_export_csv)
        btn_layout.addWidget(self.btn_export_pdf)
        btn_layout.addStretch()

        # Splitter for Invoices and Items
        splitter = QSplitter(Qt.Vertical)

        # Top: Invoices Table
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("Invoices"))
        
        self.invoice_table = QTableView()
        self.invoice_model = InvoiceTableModel(self)
        self.invoice_table.setModel(self.invoice_model)
        self.invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.invoice_table.setSelectionBehavior(QTableView.SelectRows)
        self.invoice_table.setSelectionMode(QTableView.SingleSelection)
        self.invoice_table.selectionModel().selectionChanged.connect(self.on_invoice_selected)
        top_layout.addWidget(self.invoice_table)

        # Pagination
        from src.ui.widgets.pagination_widget import PaginationWidget
        self.pagination = PaginationWidget(limit=50)
        self.pagination.page_changed.connect(self._load_page)
        top_layout.addWidget(self.pagination)

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

        self.item_table = QTableView()
        self.item_model = InvoiceItemTableModel(self)
        self.item_table.setModel(self.item_model)
        self.item_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.item_table.setSelectionBehavior(QTableView.SelectRows)
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
        self.btn_export_csv.clicked.connect(self.export_csv)
        self.btn_export_pdf.clicked.connect(self.export_pdf)

        # Graceful degradation for PDF
        from src.core.pdf_engine import PDFEngine
        if not PDFEngine.is_available():
            self.btn_export_pdf.setEnabled(False)
            self.btn_export_pdf.setToolTip("PDF generation requires 'reportlab'.")

    def load_data(self):
        self.item_model.update_data([])
        self.pagination.reset()

    def _load_page(self, limit: int, offset: int):
        self.item_model.update_data([])
        try:
            total = SalesService.count_all_invoices(self.context)
            self.pagination.update_state(total)
            
            invoices = SalesService.get_all_invoices(
                self.context, limit=limit, offset=offset
            )
            self.invoice_model.update_data(invoices)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load invoices: {str(e)}")

    def on_invoice_selected(self):
        self.item_model.update_data([])
        selection = self.invoice_table.selectionModel()
        if not selection or not selection.hasSelection():
            self.btn_add_item.setEnabled(False)
            return

        row = selection.selectedRows()[0].row()
        invoice_id = self.invoice_model.get_entity_id_at(row)
        invoice_entity = self.invoice_model.get_entity_at(row)
        state = invoice_entity.state.value if invoice_entity and invoice_entity.state else ""
        
        # Only allow adding items if state is Draft
        self.btn_add_item.setEnabled(state == "Draft")

        try:
            invoice = SalesService.get_invoice_with_items(self.context, invoice_id)
            if invoice and invoice.items:
                self.item_model.update_data(invoice.items)
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
        selection = self.invoice_table.selectionModel()
        if not selection or not selection.hasSelection():
            return
        
        row = selection.selectedRows()[0].row()
        invoice_id = self.invoice_model.get_entity_id_at(row)

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
                for i in range(self.invoice_model.rowCount()):
                    if self.invoice_model.get_entity_id_at(i) == invoice_id:
                        self.invoice_table.selectRow(i)
                        break
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add item: {str(e)}")

    def validate_invoice(self):
        selection = self.invoice_table.selectionModel()
        if not selection or not selection.hasSelection():
            QMessageBox.warning(self, "Selection Required", "Please select an invoice to validate.")
            return

        row = selection.selectedRows()[0].row()
        invoice_id = self.invoice_model.get_entity_id_at(row)
        invoice_entity = self.invoice_model.get_entity_at(row)
        state = invoice_entity.state.value if invoice_entity and invoice_entity.state else ""

        if state != "Draft":
            QMessageBox.warning(self, "Invalid State", "Only Draft invoices can be validated.")
            return

        reply = QMessageBox.question(self, "Confirm Validation", 
                                     "Are you sure you want to validate this invoice? This will decrease stock and generate incoming financial entries.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.btn_validate.setEnabled(False)
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
            finally:
                self.btn_validate.setEnabled(True)

    def export_csv(self):
        import os
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop_path) or not os.path.isdir(desktop_path):
            desktop_path = os.path.expanduser("~")
        filepath = os.path.join(desktop_path, "Invoices_Export.csv")
        try:
            self.invoice_model.export_to_csv(filepath)
            QMessageBox.information(self, "Export Successful", f"Data exported to:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export CSV: {str(e)}")

    def export_pdf(self):
        selection = self.invoice_table.selectionModel()
        if not selection or not selection.hasSelection():
            QMessageBox.warning(self, "Selection Required", "Please select an invoice to export.")
            return

        row = selection.selectedRows()[0].row()
        invoice_entity = self.invoice_model.get_entity_at(row)
        
        if not invoice_entity:
            return

        invoice_data = {
            "invoice_number": invoice_entity.invoice_number,
            "customer_id": invoice_entity.customer_id,
            "total_amount": float(invoice_entity.total_amount)
        }
        
        # Re-fetch with items to ensure we have them
        try:
            invoice = SalesService.get_invoice_with_items(self.context, invoice_entity.id)
            items_data = []
            if invoice and invoice.items:
                for item in invoice.items:
                    items_data.append({
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "unit_price": float(item.unit_price),
                        "vat_rate": float(item.vat_rate)
                    })
            
            from src.core.pdf_engine import PDFEngine
            filepath = PDFEngine.generate_invoice_pdf(invoice_data, items_data)
            QMessageBox.information(self, "PDF Exported", f"Invoice PDF saved to:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {str(e)}")
