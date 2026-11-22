from PySide6.QtWidgets import QComboBox, QDialogButtonBox, QFormLayout, QLineEdit

from src.modules.parties import PartyType, as_party_type
from src.ui.dialogs.base_dialog import FormDialog


class CustomerDialog(FormDialog):
    def __init__(self, customer=None, parent=None):
        self.customer = customer
        super().__init__(
            title="Edit Customer" if customer else "New Customer",
            subtitle="Companies and individuals are both accepted.",
            min_width=460,
            parent=parent,
        )
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.party_type_input = QComboBox()
        self.party_type_input.addItem("Entreprise", PartyType.ENTERPRISE.value)
        self.party_type_input.addItem("Individuel", PartyType.INDIVIDUAL.value)

        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("e.g. Froid Atlas SARL")
        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("Prénom")
        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("Nom de famille")
        self.contact_name_input = QLineEdit()
        self.contact_name_input.setPlaceholderText("Person to contact")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("name@company.ma")
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("e.g. 06 12 34 56 78")
        self.ice_number_input = QLineEdit()
        self.ice_number_input.setPlaceholderText("ICE (15 digits, companies)")

        form.addRow("Type *", self.party_type_input)
        form.addRow("Company Name *", self.company_name_input)
        form.addRow("First Name *", self.first_name_input)
        form.addRow("Last Name", self.last_name_input)
        form.addRow("Contact Name", self.contact_name_input)
        form.addRow("Email", self.email_input)
        form.addRow("Phone", self.phone_input)
        form.addRow("ICE Number", self.ice_number_input)

        self.party_type_input.currentIndexChanged.connect(self._update_party_fields)
        self._update_party_fields()

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            ok_text="Save Customer",
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def _update_party_fields(self):
        """A company has a name; an individual has a first and last name."""
        is_company = self.party_type_input.currentData() == PartyType.ENTERPRISE.value
        self.form.setRowVisible(self.company_name_input, is_company)
        self.form.setRowVisible(self.first_name_input, not is_company)
        self.form.setRowVisible(self.last_name_input, not is_company)

    def load_data(self):
        if self.customer:
            kind = as_party_type(self.customer.party_type)
            index = self.party_type_input.findData(kind.value)
            self.party_type_input.setCurrentIndex(max(0, index))
            self.company_name_input.setText(self.customer.company_name or "")
            self.first_name_input.setText(self.customer.first_name or "")
            self.last_name_input.setText(self.customer.last_name or "")
            self.contact_name_input.setText(self.customer.contact_name or "")
            self.email_input.setText(self.customer.email or "")
            self.phone_input.setText(self.customer.phone or "")
            self.ice_number_input.setText(self.customer.ice_number or "")
            self._update_party_fields()

    def validate_and_accept(self):
        from PySide6.QtWidgets import QMessageBox

        is_company = self.party_type_input.currentData() == PartyType.ENTERPRISE.value
        if is_company and not self.company_name_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Company Name is required.")
            return
        if not is_company and not self.first_name_input.text().strip():
            QMessageBox.warning(
                self, "Validation Error", "First Name is required for an individual."
            )
            return

        email = self.email_input.text().strip()
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            QMessageBox.warning(self, "Validation Error", "Please enter a valid email address.")
            return

        ice = self.ice_number_input.text().strip()
        if ice and (not ice.isdigit() or len(ice) != 15):
            QMessageBox.warning(self, "Validation Error", "ICE number must be exactly 15 digits.")
            return

        self.accept()

    def get_data(self):
        return {
            "party_type": self.party_type_input.currentData(),
            "company_name": self.company_name_input.text().strip() or None,
            "first_name": self.first_name_input.text().strip() or None,
            "last_name": self.last_name_input.text().strip() or None,
            "contact_name": self.contact_name_input.text().strip() or None,
            "email": self.email_input.text().strip() or None,
            "phone": self.phone_input.text().strip() or None,
            "ice_number": self.ice_number_input.text().strip() or None,
        }
