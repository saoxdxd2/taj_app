from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QMessageBox)
from PySide6.QtCore import Qt
from src.modules.suppliers.services import SupplierService
from src.ui.dialogs.supplier_dialog import SupplierDialog

class SupplierWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_table()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_add = QPushButton("Add Supplier")
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
        self.btn_add.clicked.connect(self.on_add_supplier)
        self.btn_edit.clicked.connect(self.on_edit_supplier)
        self.btn_archive.clicked.connect(self.on_archive_supplier)

    def refresh_table(self):
        from src.core.session import CurrentSession
        self.table.setRowCount(0)
        try:
            suppliers = SupplierService.get_all_suppliers(CurrentSession.get_context())
            for row, s in enumerate(suppliers):
                self.table.insertRow(row)
                
                item_id = QTableWidgetItem(str(s.id))
                item_id.setData(Qt.UserRole, s.id) # Store hidden ID
                
                self.table.setItem(row, 0, item_id)
                self.table.setItem(row, 1, QTableWidgetItem(s.company_name or ""))
                self.table.setItem(row, 2, QTableWidgetItem(s.contact_name or ""))
                self.table.setItem(row, 3, QTableWidgetItem(s.email or ""))
                self.table.setItem(row, 4, QTableWidgetItem(s.phone or ""))
                
                status = "Archived" if s.is_archived else "Active"
                self.table.setItem(row, 5, QTableWidgetItem(status))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def get_selected_supplier_id(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        return selected[0].data(Qt.UserRole)

    def on_add_supplier(self):
        from src.core.session import CurrentSession
        dialog = SupplierDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                SupplierService.create_supplier(
                    context=CurrentSession.get_context(),
                    **data
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
        self.refresh_table()

    def on_edit_supplier(self):
        from src.core.session import CurrentSession
        supplier_id = self.get_selected_supplier_id()
        if not supplier_id:
            QMessageBox.warning(self, "Warning", "Please select a supplier to edit.")
            return
            
        try:
            supplier = SupplierService.get_supplier_by_id(CurrentSession.get_context(), supplier_id)
            dialog = SupplierDialog(supplier=supplier, parent=self)
            if dialog.exec():
                data = dialog.get_data()
                SupplierService.update_supplier(
                    context=CurrentSession.get_context(),
                    supplier_id=supplier_id,
                    **data
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
        self.refresh_table()

    def on_archive_supplier(self):
        from src.core.session import CurrentSession
        supplier_id = self.get_selected_supplier_id()
        if not supplier_id:
            QMessageBox.warning(self, "Warning", "Please select a supplier to archive.")
            return
            
        reply = QMessageBox.question(self, "Confirm Archive", "Are you sure you want to archive this supplier?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                SupplierService.archive_supplier(CurrentSession.get_context(), supplier_id=supplier_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                
        self.refresh_table()
