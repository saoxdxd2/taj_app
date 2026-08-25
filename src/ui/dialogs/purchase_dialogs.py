from PySide6.QtWidgets import (QFormLayout, QComboBox,
                               QLineEdit, QDialogButtonBox, QMessageBox, QSpinBox, QDoubleSpinBox)
from PySide6.QtCore import Qt

from src.modules.suppliers.services import SupplierService
from src.modules.inventory.services import InventoryService
from src.ui.dialogs.base_dialog import FormDialog


class NewPurchaseDialog(FormDialog):
    def __init__(self, context, parent=None):
        self.context = context
        super().__init__(
            title="New Purchase",
            subtitle="Creates a draft purchase order you can add items to.",
            min_width=460,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("e.g. PO-2026-014")

        self.supplier_combo = QComboBox()
        self.suppliers = SupplierService.get_all_suppliers(self.context)
        for s in self.suppliers:
            if not s.is_archived:
                self.supplier_combo.addItem(s.company_name, userData=s.id)

        form.addRow("Reference *", self.reference_input)
        form.addRow("Supplier *", self.supplier_combo)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Create Draft"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def validate_and_accept(self):
        if not self.reference_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Reference is required.")
            return
        if self.supplier_combo.currentData() is None:
            QMessageBox.warning(
                self, "Validation Error",
                "Please select a supplier. Add a supplier first."
            )
            return

        self.accept()

    def get_data(self):
        return {
            "reference": self.reference_input.text().strip(),
            "supplier_id": self.supplier_combo.currentData()
        }


class PurchaseAddItemDialog(FormDialog):
    def __init__(self, context, parent=None):
        self.context = context
        super().__init__(
            title="Add Item to Purchase",
            min_width=480,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.product_combo = QComboBox()
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 999999)

        self.unit_cost_input = QDoubleSpinBox()
        self.unit_cost_input.setRange(0, 9999999.99)
        self.unit_cost_input.setDecimals(2)
        self.unit_cost_input.setSuffix(" DH")
        self.unit_cost_input.setAlignment(Qt.AlignRight)

        # Populate products
        self.products = InventoryService.get_all_products(context=self.context)
        for p in self.products:
            # We can buy draft or active products
            if p.state.value != "Archived":
                self.product_combo.addItem(f"[{p.sku}] {p.name}", userData=p.id)

        form.addRow("Product *", self.product_combo)
        form.addRow("Quantity *", self.quantity_input)
        form.addRow("Unit Cost *", self.unit_cost_input)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Add Item"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def validate_and_accept(self):
        if self.product_combo.currentData() is None:
            QMessageBox.warning(
                self, "Validation Error",
                "Please select a product. Add products in Inventory first."
            )
            return
        self.accept()

    def get_data(self):
        from decimal import Decimal
        return {
            "product_id": self.product_combo.currentData(),
            "quantity": self.quantity_input.value(),
            "unit_cost": Decimal(str(self.unit_cost_input.value()))
        }