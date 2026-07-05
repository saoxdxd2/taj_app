from PySide6.QtCore import Qt, QModelIndex
from typing import Any
from src.ui.models.base_model import BaseTableModel
from src.modules.purchasing.models import Purchase, PurchaseItem

class PurchaseTableModel(BaseTableModel):
    """
    Lightweight Model for Purchase entities.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["ID", "Reference", "Supplier ID", "State", "Total Amount"]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
            
        if role == Qt.DisplayRole:
            purchase: Purchase = self._data[index.row()]
            col = index.column()
            
            if col == 0:
                return str(purchase.id)
            elif col == 1:
                return purchase.reference or ""
            elif col == 2:
                return str(purchase.supplier_id)
            elif col == 3:
                return purchase.state.value if purchase.state else ""
            elif col == 4:
                return f"{purchase.total_amount:.2f}" if purchase.total_amount is not None else ""
                
        if role == Qt.UserRole:
            return self.get_entity_id_at(index.row())
            
        return None


class PurchaseItemTableModel(BaseTableModel):
    """
    Lightweight Model for PurchaseItem entities.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["Item ID", "Product ID", "Quantity", "Unit Cost"]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
            
        if role == Qt.DisplayRole:
            item: PurchaseItem = self._data[index.row()]
            col = index.column()
            
            if col == 0:
                return str(item.id)
            elif col == 1:
                return str(item.product_id)
            elif col == 2:
                return str(item.quantity)
            elif col == 3:
                return f"{item.unit_cost:.2f}" if item.unit_cost is not None else ""
                
        if role == Qt.UserRole:
            return self.get_entity_id_at(index.row())
            
        return None
