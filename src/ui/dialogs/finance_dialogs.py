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

        self.party_combo = QComboBox()
        self.customers = CRMService.get_all_customers(context=self.context)
        self.suppliers = SupplierService.get_all_suppliers(context=self.context)
        # Walk-in / unknown parties are allowed: pick "Unknown" and just
        # type the name — no need to create a customer record first.
        self.party_combo.addItem("Unknown / walk-in (type name below)", userData=None)
        for c in self.customers:
            if not c.is_archived:
                self.party_combo.addItem(c.company_name, userData=("customer", c.id))
        for s in self.suppliers:
            if not s.is_archived:
                self.party_combo.addItem(s.company_name, userData=("supplier", s.id))

        self.unknown_party_input = QLineEdit()
        self.unknown_party_input.setPlaceholderText("Party name (for unknown / walk-in)")
        self.unknown_party_input.setVisible(False)
        self.party_combo.currentIndexChanged.connect(self._on_party_changed)

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
        form.addRow("", self.unknown_party_input)
        form.addRow("Amount *", self.amount_input)
        form.addRow("Due Date *", self.due_date_input)
        form.addRow("Bank", self.bank_input)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Save Check"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def _on_party_changed(self, index):
        is_unknown = self.party_combo.itemData(index) is None
        self.unknown_party_input.setVisible(is_unknown)

    def validate_and_accept(self):
        if not self.number_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Check number is required.")
            return
        if self.party_combo.currentData() is None and not self.unknown_party_input.text().strip():
            QMessageBox.warning(
                self, "Validation Error",
                "Type the party name, or select a known customer/supplier."
            )
            return
        self.accept()

    def get_data(self):
        from decimal import Decimal
        from datetime import datetime
        data = self.party_combo.currentData()
        if data is None:
            # Unknown / walk-in party: free-text name only
            party_kind, party_id = None, None
            party_display = self.unknown_party_input.text().strip()
        else:
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