from PySide6.QtCore import Qt, QModelIndex
from typing import Any
from src.ui.models.base_model import BaseTableModel
from src.modules.inventory.models import Product

class ProductTableModel(BaseTableModel):
    """
    Lightweight Model for Product entities.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["ID", "SKU", "Name", "Type", "State", "Purchase Price", "Sale Price"]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
            
        if role == Qt.DisplayRole:
            product: Product = self._data[index.row()]
            col = index.column()
            
            if col == 0:
                return str(product.id)
            elif col == 1:
                return product.sku or ""
            elif col == 2:
                return product.name or ""
            elif col == 3:
                return product.product_type.value if product.product_type else ""
            elif col == 4:
                return product.state.value if product.state else ""
            elif col == 5:
                return f"{product.purchase_price:.2f}" if product.purchase_price is not None else ""
            elif col == 6:
                return f"{product.sale_price:.2f}" if product.sale_price is not None else ""
                
        if role == Qt.UserRole:
            return self.get_entity_id_at(index.row())
            
        return None
