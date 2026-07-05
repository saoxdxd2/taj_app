from PySide6.QtCore import Qt, QModelIndex
from typing import Any
from src.ui.models.base_model import BaseTableModel
from src.modules.suppliers.models import Supplier

class SupplierTableModel(BaseTableModel):
    """
    Lightweight Model for Supplier entities.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["ID", "Company Name", "Contact Name", "Email", "Phone", "Status"]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
            
        if role == Qt.DisplayRole:
            supplier: Supplier = self._data[index.row()]
            col = index.column()
            
            if col == 0:
                return str(supplier.id)
            elif col == 1:
                return supplier.company_name or ""
            elif col == 2:
                return supplier.contact_name or ""
            elif col == 3:
                return supplier.email or ""
            elif col == 4:
                return supplier.phone or ""
            elif col == 5:
                return "Archived" if supplier.is_archived else "Active"
                
        if role == Qt.UserRole:
            return self.get_entity_id_at(index.row())
            
        return None
