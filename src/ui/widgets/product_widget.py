from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTableView, 
                               QHeaderView, QMessageBox)
from PySide6.QtCore import Qt
from src.modules.inventory.services import InventoryService
from src.ui.dialogs.product_dialog import ProductDialog
from src.ui.models.product_model import ProductTableModel
from src.modules.inventory.models import ProductState

class ProductWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_table()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_add = QPushButton("Add Product")
        self.btn_edit = QPushButton("Edit")
        self.btn_activate = QPushButton("Activate")
        self.btn_archive = QPushButton("Archive")
        self.btn_export_csv = QPushButton("Export CSV")
        
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_activate)
        toolbar.addWidget(self.btn_archive)
        toolbar.addWidget(self.btn_export_csv)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.table = QTableView()
        self.table_model = ProductTableModel(self)
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
        self.btn_add.clicked.connect(self.on_add_product)
        self.btn_edit.clicked.connect(self.on_edit_product)
        self.btn_activate.clicked.connect(self.on_activate_product)
        self.btn_archive.clicked.connect(self.on_archive_product)
        self.btn_export_csv.clicked.connect(self.export_csv)

    def export_csv(self):
        import os
        from PySide6.QtWidgets import QMessageBox
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop_path) or not os.path.isdir(desktop_path):
            desktop_path = os.path.expanduser("~")
        filepath = os.path.join(desktop_path, "Products_Export.csv")
        try:
            self.table_model.export_to_csv(filepath)
            QMessageBox.information(self, "Export Successful", f"Data exported to:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export CSV: {str(e)}")

    def refresh_table(self):
        self.pagination.reset()

    def _load_page(self, limit: int, offset: int):
        from src.core.session import CurrentSession
        try:
            total = InventoryService.count_all_products(CurrentSession.get_context())
            self.pagination.update_state(total)
            
            products = InventoryService.get_all_products(
                CurrentSession.get_context(), limit=limit, offset=offset
            )
            self.table_model.update_data(products)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def get_selected_product_id(self):
        selection = self.table.selectionModel()
        if not selection or not selection.hasSelection():
            return None
        return self.table_model.get_entity_id_at(selection.selectedRows()[0].row())

    def on_add_product(self):
        from src.core.session import CurrentSession
        dialog = ProductDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                InventoryService.create_product(
                    context=CurrentSession.get_context(),
                    **data
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
        self.refresh_table()

    def on_edit_product(self):
        from src.core.session import CurrentSession
        product_id = self.get_selected_product_id()
        if not product_id:
            QMessageBox.warning(self, "Warning", "Please select a product to edit.")
            return
            
        try:
            product = InventoryService.get_product_by_id(CurrentSession.get_context(), product_id)
            dialog = ProductDialog(product=product, parent=self)
            if dialog.exec():
                data = dialog.get_data()
                InventoryService.update_product(
                    context=CurrentSession.get_context(),
                    product_id=product_id,
                    **data
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
        self.refresh_table()

    def on_activate_product(self):
        from src.core.session import CurrentSession
        product_id = self.get_selected_product_id()
        if not product_id:
            QMessageBox.warning(self, "Warning", "Please select a product to activate.")
            return
            
        try:
            InventoryService.activate_product(CurrentSession.get_context(), product_id=product_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
        self.refresh_table()

    def on_archive_product(self):
        from src.core.session import CurrentSession
        product_id = self.get_selected_product_id()
        if not product_id:
            QMessageBox.warning(self, "Warning", "Please select a product to archive.")
            return
            
        reply = QMessageBox.question(self, "Confirm Archive", "Are you sure you want to archive this product?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                InventoryService.archive_product(CurrentSession.get_context(), product_id=product_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                
        self.refresh_table()
