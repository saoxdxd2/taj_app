from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QMessageBox)
from PySide6.QtCore import Qt
from src.modules.crm.services import CRMService
from src.ui.dialogs.customer_dialog import CustomerDialog

class CustomerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_table()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_add = QPushButton("Add Customer")
        self.btn_edit = QPushButton("Edit")
        self.btn_archive = QPushButton("Archive")
        
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_archive)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Company Name", "Contact Name", "Email", "Phone", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        
        # Connections
        self.btn_refresh.clicked.connect(self.refresh_table)
        self.btn_add.clicked.connect(self.on_add_customer)
        self.btn_edit.clicked.connect(self.on_edit_customer)
        self.btn_archive.clicked.connect(self.on_archive_customer)

    def refresh_table(self):
        from src.core.session import CurrentSession
        self.table.setRowCount(0)
        try:
            customers = CRMService.get_all_customers(CurrentSession.get_context())
            for row, c in enumerate(customers):
                self.table.insertRow(row)
                
                item_id = QTableWidgetItem(str(c.id))
                item_id.setData(Qt.UserRole, c.id) # Store hidden ID
                
                self.table.setItem(row, 0, item_id)
                self.table.setItem(row, 1, QTableWidgetItem(c.company_name or ""))
                self.table.setItem(row, 2, QTableWidgetItem(c.contact_name or ""))
                self.table.setItem(row, 3, QTableWidgetItem(c.email or ""))
                self.table.setItem(row, 4, QTableWidgetItem(c.phone or ""))
                
                status = "Archived" if c.is_archived else "Active"
                self.table.setItem(row, 5, QTableWidgetItem(status))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def get_selected_customer_id(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        return selected[0].data(Qt.UserRole)

    def on_add_customer(self):
        from src.core.session import CurrentSession
        dialog = CustomerDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                CRMService.create_customer(
                    context=CurrentSession.get_context(),
                    **data
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
        self.refresh_table()

    def on_edit_customer(self):
        from src.core.session import CurrentSession
        customer_id = self.get_selected_customer_id()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer to edit.")
            return
            
        try:
            # Reusing get_all_customers to find the specific customer to avoid adding a new method
            # if we don't strictly have to, though adding it is better. I will add get_customer_by_id later.
            customer = CRMService.get_customer_by_id(CurrentSession.get_context(), customer_id)
            dialog = CustomerDialog(customer=customer, parent=self)
            if dialog.exec():
                data = dialog.get_data()
                CRMService.update_customer(
                    context=CurrentSession.get_context(),
                    customer_id=customer_id,
                    **data
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
        self.refresh_table()

    def on_archive_customer(self):
        from src.core.session import CurrentSession
        customer_id = self.get_selected_customer_id()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer to archive.")
            return
            
        reply = QMessageBox.question(self, "Confirm Archive", "Are you sure you want to archive this customer?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                CRMService.archive_customer(CurrentSession.get_context(), customer_id=customer_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                
        self.refresh_table()
