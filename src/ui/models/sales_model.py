from PySide6.QtCore import Qt, QModelIndex
from typing import Any
from src.ui.models.base_model import BaseTableModel
from src.modules.sales.models import Invoice, InvoiceItem

class InvoiceTableModel(BaseTableModel):
    """
    Lightweight Model for Invoice entities.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["ID", "Invoice Number", "Customer ID", "State", "Total Amount"]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
            
        if role == Qt.DisplayRole:
            invoice: Invoice = self._data[index.row()]
            col = index.column()
            
            if col == 0:
                return str(invoice.id)
            elif col == 1:
                return invoice.invoice_number or ""
            elif col == 2:
                return str(invoice.customer_id)
            elif col == 3:
                return invoice.state.value if invoice.state else ""
            elif col == 4:
                return f"{invoice.total_amount:.2f}" if invoice.total_amount is not None else ""
                
        if role == Qt.UserRole:
            return self.get_entity_id_at(index.row())
            
        return None


class InvoiceItemTableModel(BaseTableModel):
    """
    Lightweight Model for InvoiceItem entities.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["Item ID", "Product ID", "Quantity", "Unit Price"]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
            
        if role == Qt.DisplayRole:
            item: InvoiceItem = self._data[index.row()]
            col = index.column()
            
            if col == 0:
                return str(item.id)
            elif col == 1:
                return str(item.product_id)
            elif col == 2:
                return str(item.quantity)
            elif col == 3:
                return f"{item.unit_price:.2f}" if item.unit_price is not None else ""
                
        if role == Qt.UserRole:
            return self.get_entity_id_at(index.row())
            
        return None
