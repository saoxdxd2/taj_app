from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QMessageBox)
from PySide6.QtCore import Qt
from src.modules.inventory.services import InventoryService
from src.ui.dialogs.product_dialog import ProductDialog
from src.modules.inventory.models import ProductState

class ProductWidget(QWidget):
    def __init__(self, session_maker, parent=None):
        super().__init__(parent)
        self.session_maker = session_maker
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
        
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_activate)
        toolbar.addWidget(self.btn_archive)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "SKU", "Name", "Type", "State", "Purchase Price", "Sale Price"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        
        # Connections
        self.btn_refresh.clicked.connect(self.refresh_table)
        self.btn_add.clicked.connect(self.on_add_product)
        self.btn_edit.clicked.connect(self.on_edit_product)
        self.btn_activate.clicked.connect(self.on_activate_product)
        self.btn_archive.clicked.connect(self.on_archive_product)

    def refresh_table(self):
        from src.core.session import CurrentSession
        self.table.setRowCount(0)
        with self.session_maker() as session:
            products = InventoryService.get_all_products(CurrentSession.get_context(), session)
            for row, p in enumerate(products):
                self.table.insertRow(row)
                
                item_id = QTableWidgetItem(str(p.id))
                item_id.setData(Qt.UserRole, p.id) # Store hidden ID
                
                self.table.setItem(row, 0, item_id)
                self.table.setItem(row, 1, QTableWidgetItem(p.sku))
                self.table.setItem(row, 2, QTableWidgetItem(p.name))
                self.table.setItem(row, 3, QTableWidgetItem(p.product_type.value))
                self.table.setItem(row, 4, QTableWidgetItem(p.state.value))
                self.table.setItem(row, 5, QTableWidgetItem(f"{p.purchase_price:.2f}"))
                self.table.setItem(row, 6, QTableWidgetItem(f"{p.sale_price:.2f}"))

    def get_selected_product_id(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        return selected[0].data(Qt.UserRole)

    def on_add_product(self):
        from src.core.session import CurrentSession
        with self.session_maker() as session:
            dialog = ProductDialog(session, parent=self)
            if dialog.exec():
                data = dialog.get_data()
                try:
                    InventoryService.create_product(
                        context=CurrentSession.get_context(),
                        session=session,
                        **data
                    )
                    session.commit()
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", str(e))
        self.refresh_table()

    def on_edit_product(self):
        from src.core.session import CurrentSession
        product_id = self.get_selected_product_id()
        if not product_id:
            QMessageBox.warning(self, "Warning", "Please select a product to edit.")
            return
            
        with self.session_maker() as session:
            # Need to get product
            from src.modules.inventory.models import Product
            product = session.query(Product).filter(Product.id == product_id).first()
            
            dialog = ProductDialog(session, product=product, parent=self)
            if dialog.exec():
                data = dialog.get_data()
                try:
                    InventoryService.update_product(
                        context=CurrentSession.get_context(),
                        session=session,
                        product_id=product_id,
                        **data
                    )
                    session.commit()
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", str(e))
        self.refresh_table()

    def on_activate_product(self):
        from src.core.session import CurrentSession
        product_id = self.get_selected_product_id()
        if not product_id:
            QMessageBox.warning(self, "Warning", "Please select a product to activate.")
            return
            
        with self.session_maker() as session:
            try:
                InventoryService.activate_product(CurrentSession.get_context(), session, product_id)
                session.commit()
            except Exception as e:
                session.rollback()
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
            with self.session_maker() as session:
                try:
                    InventoryService.archive_product(CurrentSession.get_context(), session, product_id)
                    session.commit()
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self, "Error", str(e))
            self.refresh_table()
