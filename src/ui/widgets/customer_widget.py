from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTableView, 
                               QHeaderView, QMessageBox)
from PySide6.QtCore import Qt
from src.modules.crm.services import CRMService
from src.ui.dialogs.customer_dialog import CustomerDialog
from src.ui.models.customer_model import CustomerTableModel

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
        self.table = QTableView()
        self.table_model = CustomerTableModel(self)
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        layout.addWidget(self.table)
        
        # Pagination
        from src.ui.widgets.pagination_widget import PaginationWidget
        self.pagination = PaginationWidget(limit=50)
        self.pagination.page_changed.connect(self._load_page)
        layout.addWidget(self.pagination)
        
        # Connections
        self.btn_refresh.clicked.connect(self.refresh_table)
        self.btn_add.clicked.connect(self.on_add_customer)
        self.btn_edit.clicked.connect(self.on_edit_customer)
        self.btn_archive.clicked.connect(self.on_archive_customer)

    def refresh_table(self):
        self.pagination.reset()

    def _load_page(self, limit: int, offset: int):
        from src.core.session import CurrentSession
        try:
            total = CRMService.count_all_customers(CurrentSession.get_context())
            self.pagination.update_state(total)
            
            customers = CRMService.get_all_customers(
                CurrentSession.get_context(), limit=limit, offset=offset
            )
            self.table_model.update_data(customers)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def get_selected_customer_id(self):
        selection = self.table.selectionModel()
        if not selection or not selection.hasSelection():
            return None
        return self.table_model.get_entity_id_at(selection.selectedRows()[0].row())

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
