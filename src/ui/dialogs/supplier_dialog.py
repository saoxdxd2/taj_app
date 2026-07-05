from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                               QLineEdit, QDialogButtonBox, QMessageBox)

class SupplierDialog(QDialog):
    def __init__(self, supplier=None, parent=None):
        super().__init__(parent)
        self.supplier = supplier
        self.setWindowTitle("Edit Supplier" if supplier else "Create Supplier")
        
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.company_name_input = QLineEdit()
        self.contact_name_input = QLineEdit()
        self.email_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.ice_number_input = QLineEdit()

        form_layout.addRow("Company Name*", self.company_name_input)
        form_layout.addRow("Contact Name", self.contact_name_input)
        form_layout.addRow("Email", self.email_input)
        form_layout.addRow("Phone", self.phone_input)
        form_layout.addRow("ICE Number", self.ice_number_input)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def load_data(self):
        if self.supplier:
            self.company_name_input.setText(self.supplier.company_name or "")
            self.contact_name_input.setText(self.supplier.contact_name or "")
            self.email_input.setText(self.supplier.email or "")
            self.phone_input.setText(self.supplier.phone or "")
            self.ice_number_input.setText(self.supplier.ice_number or "")

    def validate_and_accept(self):
        if not self.company_name_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Company Name is required.")
            return
            
        self.accept()

    def get_data(self):
        return {
            "company_name": self.company_name_input.text().strip(),
            "contact_name": self.contact_name_input.text().strip() or None,
            "email": self.email_input.text().strip() or None,
            "phone": self.phone_input.text().strip() or None,
            "ice_number": self.ice_number_input.text().strip() or None
        }
