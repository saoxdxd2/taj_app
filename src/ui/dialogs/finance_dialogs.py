from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
                               QLineEdit, QDialogButtonBox, QMessageBox,
                               QDoubleSpinBox, QDateEdit)
from PySide6.QtCore import QDate

from src.modules.crm.services import CRMService
from src.modules.suppliers.services import SupplierService


class NewCheckDialog(QDialog):
    """Register an incoming (customer) or outgoing (supplier) check."""

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("New Check")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout(self)

        self.number_input = QLineEdit()
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Incoming (from customer)", userData="Incoming")
        self.direction_combo.addItem("Outgoing (to supplier)", userData="Outgoing")

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

        self.due_date_input = QDateEdit(QDate.currentDate().addDays(30))
        self.due_date_input.setCalendarPopup(True)

        self.bank_input = QLineEdit()
        self.bank_input.setPlaceholderText("Bank (optional)")

        form.addRow("Check Number*", self.number_input)
        form.addRow("Direction*", self.direction_combo)
        form.addRow("Party*", self.party_combo)
        form.addRow("Amount*", self.amount_input)
        form.addRow("Due Date*", self.due_date_input)
        form.addRow("Bank", self.bank_input)
        layout.addLayout(form)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def validate_and_accept(self):
        if not self.number_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Check number is required.")
            return
        if self.party_combo.currentData() is None:
            QMessageBox.warning(self, "Validation Error", "Please select a party.")
            return
        self.accept()

    def get_data(self):
        from decimal import Decimal
        from datetime import datetime
        party_kind, party_id = self.party_combo.currentData()
        due = self.due_date_input.date()
        return {
            "check_number": self.number_input.text().strip(),
            "direction": self.direction_combo.currentData(),
            "amount": Decimal(str(self.amount_input.value())),
            "due_date": datetime(due.year(), due.month(), due.day()),
            "party_name": self.party_combo.currentText(),
            "bank": self.bank_input.text().strip() or None,
            "customer_id": party_id if party_kind == "customer" else None,
            "supplier_id": party_id if party_kind == "supplier" else None,
        }