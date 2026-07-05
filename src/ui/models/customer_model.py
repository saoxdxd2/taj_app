from PySide6.QtCore import Qt, QModelIndex
from typing import Any
from src.ui.models.base_model import BaseTableModel
from src.modules.crm.models import Customer

class CustomerTableModel(BaseTableModel):
    """
    Lightweight Model for Customer entities.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["ID", "Company Name", "Contact Name", "Email", "Phone", "Status"]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
            
        if role == Qt.DisplayRole:
            customer: Customer = self._data[index.row()]
            col = index.column()
            
            if col == 0:
                return str(customer.id)
            elif col == 1:
                return customer.company_name or ""
            elif col == 2:
                return customer.contact_name or ""
            elif col == 3:
                return customer.email or ""
            elif col == 4:
                return customer.phone or ""
            elif col == 5:
                return "Archived" if customer.is_archived else "Active"
                
        # Support fetching the ID via UserRole (similar to how QTableWidgetItem did)
        if role == Qt.UserRole:
            return self.get_entity_id_at(index.row())
            
        return None
