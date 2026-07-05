from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                               QLineEdit, QComboBox, QDoubleSpinBox, 
                               QDialogButtonBox, QMessageBox)
from src.modules.inventory.models import ProductType, ProductState
from decimal import Decimal

class ProductDialog(QDialog):
    def __init__(self, product=None, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle("Edit Product" if product else "Create Product")
        
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.sku_input = QLineEdit()
        
        self.type_combo = QComboBox()
        for t in ProductType:
            self.type_combo.addItem(t.value, t)
            
        self.purchase_price_input = QDoubleSpinBox()
        self.purchase_price_input.setRange(0, 999999999)
        self.purchase_price_input.setDecimals(2)
        
        self.sale_price_input = QDoubleSpinBox()
        self.sale_price_input.setRange(0, 999999999)
        self.sale_price_input.setDecimals(2)
        
        self.vat_input = QDoubleSpinBox()
        self.vat_input.setRange(0, 100)
        self.vat_input.setDecimals(2)
        self.vat_input.setValue(20.00)

        # Simplified: Brands and Categories could be combo boxes populated from DB
        from src.modules.inventory.services import InventoryService
        from src.core.session import CurrentSession
        context = CurrentSession.get_context()
        self.brands = InventoryService.get_all_brands(context=context)
        self.categories = InventoryService.get_all_categories(context=context)
        
        self.brand_combo = QComboBox()
        self.brand_combo.addItem("None", None)
        for b in self.brands:
            self.brand_combo.addItem(b.name, b.id)
            
        self.category_combo = QComboBox()
        self.category_combo.addItem("None", None)
        for c in self.categories:
            self.category_combo.addItem(c.name, c.id)

        form_layout.addRow("Name*", self.name_input)
        form_layout.addRow("SKU*", self.sku_input)
        form_layout.addRow("Type", self.type_combo)
        form_layout.addRow("Purchase Price", self.purchase_price_input)
        form_layout.addRow("Sale Price", self.sale_price_input)
        form_layout.addRow("VAT Rate (%)", self.vat_input)
        form_layout.addRow("Brand", self.brand_combo)
        form_layout.addRow("Category", self.category_combo)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def load_data(self):
        if self.product:
            self.name_input.setText(self.product.name)
            self.sku_input.setText(self.product.sku)
            self.type_combo.setCurrentText(self.product.product_type.value)
            self.purchase_price_input.setValue(float(self.product.purchase_price))
            self.sale_price_input.setValue(float(self.product.sale_price))
            self.vat_input.setValue(float(self.product.vat_rate))
            
            if self.product.brand_id:
                idx = self.brand_combo.findData(self.product.brand_id)
                if idx >= 0:
                    self.brand_combo.setCurrentIndex(idx)
                    
            if self.product.category_id:
                idx = self.category_combo.findData(self.product.category_id)
                if idx >= 0:
                    self.category_combo.setCurrentIndex(idx)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Name is required.")
            return
        if not self.sku_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "SKU is required.")
            return
            
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "sku": self.sku_input.text().strip(),
            "product_type": self.type_combo.currentData(),
            "purchase_price": Decimal(str(self.purchase_price_input.value())),
            "sale_price": Decimal(str(self.sale_price_input.value())),
            "vat_rate": Decimal(str(self.vat_input.value())),
            "brand_id": self.brand_combo.currentData(),
            "category_id": self.category_combo.currentData()
        }
