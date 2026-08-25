from PySide6.QtWidgets import (QFormLayout, QComboBox,
                               QLineEdit, QDialogButtonBox, QMessageBox,
                               QDoubleSpinBox, QDateEdit)
from PySide6.QtCore import Qt, QDate

from src.modules.crm.services import CRMService
from src.modules.suppliers.services import SupplierService
from src.ui.dialogs.base_dialog import FormDialog


class NewCheckDialog(FormDialog):
    """Register an incoming (customer) or outgoing (supplier) check."""

    def __init__(self, context, parent=None):
        self.context = context
        super().__init__(
            title="New Check",
            subtitle="Register an incoming (customer) or outgoing (supplier) check.",
            min_width=480,
            parent=parent,
        )
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("e.g. 004512789")

        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Incoming (from customer)", userData="Incoming")
        self.direction_combo.addItem("Outgoing (to supplier)", userData="Outgoing")

        # Checks/virements always need a known customer/supplier —
        # only cash sales can be anonymous.
        self.party_combo = QComboBox()
        self.customers = CRMService.get_all_customers(context=self.context)
        self.suppliers = SupplierService.get_all_suppliers(context=self.context)
        for c in self.customers:
            if not c.is_archived:
                self.party_combo.addItem(c.company_name, userData=("customer", c.id))
        for s in self.suppliers:
            if not s.is_archived:
                self.party_combo.addItem(s.company_name, userData=("supplier", s.id))

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, 9999999.99)
        self.amount_input.setDecimals(2)
        self.amount_input.setSuffix(" DH")
        self.amount_input.setAlignment(Qt.AlignRight)

        self.due_date_input = QDateEdit(QDate.currentDate().addDays(30))
        self.due_date_input.setCalendarPopup(True)
        self.due_date_input.setDisplayFormat("dd/MM/yyyy")

        self.bank_input = QLineEdit()
        self.bank_input.setPlaceholderText("Bank (optional)")

        form.addRow("Check Number *", self.number_input)
        form.addRow("Direction *", self.direction_combo)
        form.addRow("Party *", self.party_combo)
        form.addRow("Amount *", self.amount_input)
        form.addRow("Due Date *", self.due_date_input)
        form.addRow("Bank", self.bank_input)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Save Check"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def validate_and_accept(self):
        if not self.number_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Check number is required.")
            return
        if self.party_combo.currentData() is None:
            QMessageBox.warning(
                self, "Validation Error",
                "Please select a customer or supplier. Checks must be linked "
                "to a known account — add one first."
            )
            return
        self.accept()

    def get_data(self):
        from decimal import Decimal
        from datetime import datetime
        data = self.party_combo.currentData()
        if data is None:
            raise ValueError("No party selected.")
        party_kind, party_id = data
        party_display = self.party_combo.currentText()
        due = self.due_date_input.date()
        return {
            "check_number": self.number_input.text().strip(),
            "direction": self.direction_combo.currentData(),
            "amount": Decimal(str(self.amount_input.value())),
            "due_date": datetime(due.year(), due.month(), due.day()),
            "party_name": party_display,
            "bank": self.bank_input.text().strip() or None,
            "customer_id": party_id if party_kind == "customer" else None,
            "supplier_id": party_id if party_kind == "supplier" else None,
        }