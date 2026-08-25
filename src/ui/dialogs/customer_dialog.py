from PySide6.QtWidgets import QFormLayout, QLineEdit
from src.ui.dialogs.base_dialog import FormDialog


class CustomerDialog(FormDialog):
    def __init__(self, customer=None, parent=None):
        self.customer = customer
        super().__init__(
            title="Edit Customer" if customer else "New Customer",
            subtitle="Fields marked * are required.",
            min_width=460,
            parent=parent,
        )
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        form = QFormLayout()
        self.make_form(form)

        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("e.g. Froid Atlas SARL")
        self.contact_name_input = QLineEdit()
        self.contact_name_input.setPlaceholderText("Person to contact")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("name@company.ma")
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("e.g. 06 12 34 56 78")
        self.ice_number_input = QLineEdit()
        self.ice_number_input.setPlaceholderText("ICE (15 digits)")

        form.addRow("Company Name *", self.company_name_input)
        form.addRow("Contact Name", self.contact_name_input)
        form.addRow("Email", self.email_input)
        form.addRow("Phone", self.phone_input)
        form.addRow("ICE Number", self.ice_number_input)

        box = self.add_buttons(ok_text="Save Customer")
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

    def load_data(self):
        if self.customer:
            self.company_name_input.setText(self.customer.company_name or "")
            self.contact_name_input.setText(self.customer.contact_name or "")
            self.email_input.setText(self.customer.email or "")
            self.phone_input.setText(self.customer.phone or "")
            self.ice_number_input.setText(self.customer.ice_number or "")

    def validate_and_accept(self):
        from PySide6.QtWidgets import QMessageBox

        company = self.company_name_input.text().strip()
        if not company:
            QMessageBox.warning(self, "Validation Error", "Company Name is required.")
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
            "company_name": self.company_name_input.text().strip(),
            "contact_name": self.contact_name_input.text().strip() or None,
            "email": self.email_input.text().strip() or None,
            "phone": self.phone_input.text().strip() or None,
            "ice_number": self.ice_number_input.text().strip() or None,
        }