from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTableView, QHeaderView, QMessageBox, QSplitter, QLabel)
from PySide6.QtCore import Qt

from src.core.session import CurrentSession
from src.modules.purchasing.services import PurchasingService
from src.ui.dialogs.purchase_dialogs import NewPurchaseDialog, PurchaseAddItemDialog
from src.ui.models.purchase_model import PurchaseTableModel, PurchaseItemTableModel

class PurchaseWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = CurrentSession.get_context()
        
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Buttons - Purchases
        btn_layout = QHBoxLayout()
        self.btn_new_draft = QPushButton("New Draft Purchase")
        self.btn_validate = QPushButton("Validate Purchase")
        self.btn_refresh = QPushButton("Refresh")

        btn_layout.addWidget(self.btn_new_draft)
        btn_layout.addWidget(self.btn_validate)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()

        # Splitter for Purchases and Items
        splitter = QSplitter(Qt.Vertical)

        # Top: Purchases Table
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("Purchases"))
        
        self.purchase_table = QTableView()
        self.purchase_model = PurchaseTableModel(self)
        self.purchase_table.setModel(self.purchase_model)
        self.purchase_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.purchase_table.setSelectionBehavior(QTableView.SelectRows)
        self.purchase_table.setSelectionMode(QTableView.SingleSelection)
        self.purchase_table.selectionModel().selectionChanged.connect(self.on_purchase_selected)
        top_layout.addWidget(self.purchase_table)

        # Pagination
        from src.ui.widgets.pagination_widget import PaginationWidget
        self.pagination = PaginationWidget(limit=50)
        self.pagination.page_changed.connect(self._load_page)
        top_layout.addWidget(self.pagination)

        # Bottom: Items Table
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        item_btn_layout = QHBoxLayout()
        item_btn_layout.addWidget(QLabel("Purchase Items"))
        self.btn_add_item = QPushButton("Add Item")
        self.btn_add_item.setEnabled(False)
        item_btn_layout.addWidget(self.btn_add_item)
        item_btn_layout.addStretch()
        bottom_layout.addLayout(item_btn_layout)

        self.item_table = QTableView()
        self.item_model = PurchaseItemTableModel(self)
        self.item_table.setModel(self.item_model)
        self.item_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.item_table.setSelectionBehavior(QTableView.SelectRows)
        bottom_layout.addWidget(self.item_table)

        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        layout.addLayout(btn_layout)
        layout.addWidget(splitter)

        # Connect signals
        self.btn_new_draft.clicked.connect(self.create_draft)
        self.btn_validate.clicked.connect(self.validate_purchase)
        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_add_item.clicked.connect(self.add_item)

    def load_data(self):
        self.item_model.update_data([])
        self.pagination.reset()

    def _load_page(self, limit: int, offset: int):
        self.item_model.update_data([])
        try:
            total = PurchasingService.count_all_purchases(self.context)
            self.pagination.update_state(total)
            
            purchases = PurchasingService.get_all_purchases(
                self.context, limit=limit, offset=offset
            )
            self.purchase_model.update_data(purchases)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load purchases: {str(e)}")

    def on_purchase_selected(self):
        self.item_model.update_data([])
        selection = self.purchase_table.selectionModel()
        if not selection or not selection.hasSelection():
            self.btn_add_item.setEnabled(False)
            return

        row = selection.selectedRows()[0].row()
        purchase_id = self.purchase_model.get_entity_id_at(row)
        purchase_entity = self.purchase_model.get_entity_at(row)
        
        state = purchase_entity.state.value if purchase_entity and purchase_entity.state else ""
        
        # Only allow adding items if state is Draft
        self.btn_add_item.setEnabled(state == "Draft")

        try:
            purchase = PurchasingService.get_purchase_with_items(self.context, purchase_id)
            if purchase and purchase.items:
                self.item_model.update_data(purchase.items)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load items: {str(e)}")

    def create_draft(self):
        dialog = NewPurchaseDialog(self.context, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                PurchasingService.create_purchase_draft(
                    self.context, 
                    reference=data["reference"], 
                    supplier_id=data["supplier_id"]
                )
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create draft: {str(e)}")

    def add_item(self):
        selection = self.purchase_table.selectionModel()
        if not selection or not selection.hasSelection():
            return
        
        row = selection.selectedRows()[0].row()
        purchase_id = self.purchase_model.get_entity_id_at(row)

        dialog = PurchaseAddItemDialog(self.context, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                PurchasingService.add_item_to_purchase(
                    self.context,
                    purchase_id=purchase_id,
                    product_id=data["product_id"],
                    quantity=data["quantity"],
                    unit_cost=data["unit_cost"]
                )
                self.load_data()
                
                # Reselect the purchase to show updated items
                for i in range(self.purchase_model.rowCount()):
                    if self.purchase_model.get_entity_id_at(i) == purchase_id:
                        self.purchase_table.selectRow(i)
                        break
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add item: {str(e)}")

    def validate_purchase(self):
        selection = self.purchase_table.selectionModel()
        if not selection or not selection.hasSelection():
            QMessageBox.warning(self, "Selection Required", "Please select a purchase to validate.")
            return

        row = selection.selectedRows()[0].row()
        purchase_id = self.purchase_model.get_entity_id_at(row)
        purchase_entity = self.purchase_model.get_entity_at(row)
        state = purchase_entity.state.value if purchase_entity and purchase_entity.state else ""

        if state != "Draft":
            QMessageBox.warning(self, "Invalid State", "Only Draft purchases can be validated.")
            return

        reply = QMessageBox.question(self, "Confirm Validation", 
                                     "Are you sure you want to validate this purchase? This will update stock and generate financial entries.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.btn_validate.setEnabled(False)
            try:
                success = PurchasingService.validate_purchase(self.context, purchase_id=purchase_id)
                if success:
                    QMessageBox.information(self, "Success", "Purchase validated successfully.")
                    self.load_data()
                else:
                    QMessageBox.warning(self, "Warning", "Purchase could not be validated (may be empty).")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to validate purchase: {str(e)}")
            finally:
                self.btn_validate.setEnabled(True)
