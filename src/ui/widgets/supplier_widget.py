from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTableView, 
                               QHeaderView, QMessageBox)
from PySide6.QtCore import Qt
from src.modules.suppliers.services import SupplierService
from src.ui.dialogs.supplier_dialog import SupplierDialog
from src.ui.models.supplier_model import SupplierTableModel

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
        self.table = QTableView()
        self.table_model = SupplierTableModel(self)
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        layout.addWidget(self.table)
        
        # Connections
        self.btn_refresh.clicked.connect(self.refresh_table)
        self.btn_add.clicked.connect(self.on_add_supplier)
        self.btn_edit.clicked.connect(self.on_edit_supplier)
        self.btn_archive.clicked.connect(self.on_archive_supplier)

    def refresh_table(self):
        from src.core.session import CurrentSession
        try:
            suppliers = SupplierService.get_all_suppliers(CurrentSession.get_context())
            self.table_model.update_data(suppliers)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def get_selected_supplier_id(self):
        selection = self.table.selectionModel()
        if not selection or not selection.hasSelection():
            return None
        return self.table_model.get_entity_id_at(selection.selectedRows()[0].row())

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
