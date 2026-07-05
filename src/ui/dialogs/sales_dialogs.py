from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, 
                               QLineEdit, QDialogButtonBox, QMessageBox, QSpinBox, QDoubleSpinBox)
from PySide6.QtCore import Qt

from src.modules.crm.services import CRMService
from src.modules.inventory.services import InventoryService

class NewInvoiceDialog(QDialog):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Create Invoice Draft")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.invoice_number_input = QLineEdit()
        self.customer_combo = QComboBox()
        
        # Populate customers
        self.customers = CRMService.get_all_customers(context=self.context)
        for c in self.customers:
            if not c.is_archived:
                self.customer_combo.addItem(c.company_name, userData=c.id)

        form_layout.addRow("Invoice Number*", self.invoice_number_input)
        form_layout.addRow("Customer*", self.customer_combo)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def validate_and_accept(self):
        if not self.invoice_number_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Invoice number is required.")
            return
        if self.customer_combo.currentData() is None:
            QMessageBox.warning(self, "Validation Error", "Please select a customer.")
            return
            
        self.accept()

    def get_data(self):
        return {
            "invoice_number": self.invoice_number_input.text().strip(),
            "customer_id": self.customer_combo.currentData()
        }

class InvoiceAddItemDialog(QDialog):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Add Item to Invoice")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.product_combo = QComboBox()
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 999999)
        
        self.unit_price_input = QDoubleSpinBox()
        self.unit_price_input.setRange(0, 9999999.99)
        self.unit_price_input.setDecimals(2)

        self.vat_rate_input = QDoubleSpinBox()
        self.vat_rate_input.setRange(0, 100.00)
        self.vat_rate_input.setDecimals(2)
        self.vat_rate_input.setValue(20.00) # Default VAT
        
        # Populate products
        self.products = InventoryService.get_all_products(context=self.context)
        for p in self.products:
            if p.state.value == "Active":
                # Typically, only Active products are sold
                self.product_combo.addItem(f"[{p.sku}] {p.name}", userData=p.id)

        form_layout.addRow("Product*", self.product_combo)
        form_layout.addRow("Quantity*", self.quantity_input)
        form_layout.addRow("Unit Price*", self.unit_price_input)
        form_layout.addRow("VAT Rate (%)*", self.vat_rate_input)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Pre-fill unit price and VAT when product changes
        self.product_combo.currentIndexChanged.connect(self.on_product_changed)
        if self.product_combo.count() > 0:
            self.on_product_changed(0)

    def on_product_changed(self, index):
        product_id = self.product_combo.itemData(index)
        if product_id:
            # Find the product
            for p in self.products:
                if p.id == product_id:
                    self.unit_price_input.setValue(float(p.sale_price))
                    self.vat_rate_input.setValue(float(p.vat_rate))
                    break

    def validate_and_accept(self):
        if self.product_combo.currentData() is None:
            QMessageBox.warning(self, "Validation Error", "Please select a product.")
            return
        self.accept()

    def get_data(self):
        from decimal import Decimal
        return {
            "product_id": self.product_combo.currentData(),
            "quantity": self.quantity_input.value(),
            "unit_price": Decimal(str(self.unit_price_input.value())),
            "vat_rate": Decimal(str(self.vat_rate_input.value()))
        }
