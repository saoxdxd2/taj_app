from PySide6.QtWidgets import (QFormLayout, QComboBox, QLabel,
                               QLineEdit, QDialogButtonBox, QMessageBox, QSpinBox, QDoubleSpinBox)
from PySide6.QtCore import Qt

from src.modules.crm.services import CRMService
from src.modules.inventory.services import InventoryService
from src.modules.sales.services import SalesService
from src.ui.dialogs.base_dialog import FormDialog


class NewInvoiceDialog(FormDialog):
    def __init__(self, context, parent=None):
        self.context = context
        super().__init__(
            title="New Invoice",
            subtitle="Creates a draft invoice you can add items to.",
            min_width=460,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.invoice_number_input = QLineEdit()
        # Pre-fill with the next sequential number (N°XX-YY); still editable
        try:
            suggested = SalesService.generate_invoice_number(self.context)
            self.invoice_number_input.setText(suggested)
        except Exception:
            pass  # leave empty; service will generate at save time

        # Cash sales can be anonymous: "Walk-in" books them on a shared
        # 'Client de passage' customer — no need to create one first.
        self.customer_combo = QComboBox()
        self.customer_combo.addItem(
            "Walk-in / anonymous (cash sale)", userData=None
        )
        self.customers = CRMService.get_all_customers(context=self.context)
        for c in self.customers:
            if not c.is_archived and c.company_name != CRMService.WALK_IN_NAME:
                self.customer_combo.addItem(c.company_name, userData=c.id)

        form.addRow("Invoice Number *", self.invoice_number_input)
        form.addRow("Customer", self.customer_combo)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Create Draft"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def validate_and_accept(self):
        if not self.invoice_number_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Invoice number is required.")
            return

        self.accept()

    def get_data(self):
        return {
            "invoice_number": self.invoice_number_input.text().strip(),
            "customer_id": self.customer_combo.currentData()
        }


class InvoiceAddItemDialog(FormDialog):
    def __init__(self, context, parent=None):
        self.context = context
        super().__init__(
            title="Add Item to Invoice",
            subtitle="Unit price and VAT pre-fill from the product's sale price.",
            min_width=500,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.product_combo = QComboBox()
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 999999)

        self.unit_price_input = QDoubleSpinBox()
        self.unit_price_input.setRange(0, 9999999.99)
        self.unit_price_input.setDecimals(2)
        self.unit_price_input.setSuffix(" DH")
        self.unit_price_input.setAlignment(Qt.AlignRight)

        self.vat_rate_input = QDoubleSpinBox()
        self.vat_rate_input.setRange(0, 100.00)
        self.vat_rate_input.setDecimals(2)
        self.vat_rate_input.setSuffix(" %")
        self.vat_rate_input.setValue(20.00)  # Default VAT
        self.vat_rate_input.setAlignment(Qt.AlignRight)

        # Populate products
        self.products = InventoryService.get_all_products(context=self.context)
        for p in self.products:
            if p.state.value == "Active":
                # Typically, only Active products are sold
                self.product_combo.addItem(f"[{p.sku}] {p.name}", userData=p.id)

        self.unit_cost_input = QDoubleSpinBox()
        self.unit_cost_input.setRange(0, 9999999.99)
        self.unit_cost_input.setDecimals(2)
        self.unit_cost_input.setSuffix(" DH")
        self.unit_cost_input.setAlignment(Qt.AlignRight)
        self.unit_cost_input.setToolTip(
            "The REAL price you paid for this unit - used for exact profit calculation."
        )

        self.warranty_input = QSpinBox()
        self.warranty_input.setRange(0, 240)
        self.warranty_input.setValue(12)
        self.warranty_input.setSuffix(" months")
        self.warranty_input.setToolTip("Warranty in months (default 12).")

        form.addRow("Product *", self.product_combo)
        form.addRow("Quantity *", self.quantity_input)
        form.addRow("Sale Price *", self.unit_price_input)
        form.addRow("Your Cost (buy price)", self.unit_cost_input)
        form.addRow("VAT Rate", self.vat_rate_input)
        form.addRow("Warranty", self.warranty_input)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Add Item"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

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
            "unit_price": Decimal(str(self.unit_price_input.value())),
            "unit_cost": Decimal(str(self.unit_cost_input.value())),
            "vat_rate": Decimal(str(self.vat_rate_input.value())),
            "warranty_months": self.warranty_input.value(),
        }


class PaymentDialog(FormDialog):
    """Register a payment (cash / check / virement) against an invoice."""

    def __init__(self, context, invoice_number, balance, parent=None):
        self.context = context
        self.invoice_number = invoice_number
        self.balance = balance
        super().__init__(
            title="Register Payment",
            subtitle=f"Invoice {invoice_number} — remaining balance: {balance:,.2f} DH",
            min_width=460,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.method_combo = QComboBox()
        self.method_combo.addItem("Cash", userData="Cash")
        self.method_combo.addItem("Check", userData="Check")
        self.method_combo.addItem("Transfer", userData="Transfer")

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, float(self.balance))
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(float(self.balance))
        self.amount_input.setSuffix(" DH")
        self.amount_input.setAlignment(Qt.AlignRight)

        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("Check number or transfer ref (optional)")

        form.addRow("Method *", self.method_combo)
        form.addRow("Amount *", self.amount_input)
        form.addRow("Reference", self.reference_input)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Register Payment"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def validate_and_accept(self):
        from decimal import Decimal
        amount = Decimal(str(self.amount_input.value()))
        if amount <= 0 or amount > Decimal(str(self.balance)):
            QMessageBox.warning(self, "Validation Error", "Amount must be between 0 and the remaining balance.")
            return
        self.accept()

    def get_data(self):
        from decimal import Decimal
        return {
            "method": self.method_combo.currentData(),
            "amount": Decimal(str(self.amount_input.value())),
            "reference": self.reference_input.text().strip() or None,
        }


class DepositDialog(FormDialog):
    """Record a customer advance payment ('bon')."""

    def __init__(self, context, parent=None):
        self.context = context
        super().__init__(
            title="New Customer Deposit (Bon)",
            min_width=460,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.deposit_number_input = QLineEdit()
        self.deposit_number_input.setPlaceholderText("e.g. BON-2026-007")

        self.customer_combo = QComboBox()
        self.customers = CRMService.get_all_customers(context=self.context)
        for c in self.customers:
            if not c.is_archived:
                self.customer_combo.addItem(c.company_name, userData=c.id)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, 9999999.99)
        self.amount_input.setDecimals(2)
        self.amount_input.setSuffix(" DH")
        self.amount_input.setAlignment(Qt.AlignRight)

        self.method_combo = QComboBox()
        self.method_combo.addItem("Cash", userData="Cash")
        self.method_combo.addItem("Check", userData="Check")
        self.method_combo.addItem("Transfer", userData="Transfer")

        form.addRow("Deposit Number *", self.deposit_number_input)
        form.addRow("Customer *", self.customer_combo)
        form.addRow("Amount *", self.amount_input)
        form.addRow("Method *", self.method_combo)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Save Deposit"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def validate_and_accept(self):
        if not self.deposit_number_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Deposit number is required.")
            return
        if self.customer_combo.currentData() is None:
            QMessageBox.warning(
                self, "Validation Error",
                "Please select a customer. Add customers in CRM first."
            )
            return
        self.accept()

    def get_data(self):
        from decimal import Decimal
        return {
            "deposit_number": self.deposit_number_input.text().strip(),
            "customer_id": self.customer_combo.currentData(),
            "amount": Decimal(str(self.amount_input.value())),
            "method": self.method_combo.currentData(),
        }