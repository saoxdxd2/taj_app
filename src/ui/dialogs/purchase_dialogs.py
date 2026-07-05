from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, 
                               QLineEdit, QDialogButtonBox, QMessageBox, QSpinBox, QDoubleSpinBox)
from PySide6.QtCore import Qt

from src.modules.suppliers.services import SupplierService
from src.modules.inventory.services import InventoryService

class NewPurchaseDialog(QDialog):
    def __init__(self, context, session, parent=None):
        super().__init__(parent)
        self.context = context
        self.session = session
        self.setWindowTitle("New Draft Purchase")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.reference_input = QLineEdit()
        self.supplier_combo = QComboBox()
        
        # Populate suppliers
        self.suppliers = SupplierService.get_all_suppliers(self.context, self.session)
        for s in self.suppliers:
            # Check if archived? We shouldn't buy from archived suppliers normally, 
            # but for simplicity we show all or just active.
            if not s.is_archived:
                self.supplier_combo.addItem(s.company_name, userData=s.id)

        form_layout.addRow("Reference*", self.reference_input)
        form_layout.addRow("Supplier*", self.supplier_combo)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def validate_and_accept(self):
        if not self.reference_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Reference is required.")
            return
        if self.supplier_combo.currentData() is None:
            QMessageBox.warning(self, "Validation Error", "Please select a supplier.")
            return
            
        self.accept()

    def get_data(self):
        return {
            "reference": self.reference_input.text().strip(),
            "supplier_id": self.supplier_combo.currentData()
        }

class PurchaseAddItemDialog(QDialog):
    def __init__(self, context, session, parent=None):
        super().__init__(parent)
        self.context = context
        self.session = session
        self.setWindowTitle("Add Purchase Item")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.product_combo = QComboBox()
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 999999)
        
        self.unit_cost_input = QDoubleSpinBox()
        self.unit_cost_input.setRange(0, 9999999.99)
        self.unit_cost_input.setDecimals(2)
        
        # Populate products
        self.products = InventoryService.get_all_products(self.context, self.session)
        for p in self.products:
            # We can buy draft or active products
            if p.state.value != "Archived":
                self.product_combo.addItem(f"[{p.sku}] {p.name}", userData=p.id)

        form_layout.addRow("Product*", self.product_combo)
        form_layout.addRow("Quantity*", self.quantity_input)
        form_layout.addRow("Unit Cost*", self.unit_cost_input)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

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
            "unit_cost": Decimal(str(self.unit_cost_input.value()))
        }
