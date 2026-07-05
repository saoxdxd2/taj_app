from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from typing import List, Any

class BaseTableModel(QAbstractTableModel):
    """
    Reusable base class for all UI Table Models.
    Implements core Qt Model/View behavior.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Any] = []
        self._headers: List[str] = []

    def update_data(self, new_data: List[Any]):
        """
        Updates the internal dataset and signals the view to refresh.
        Currently uses beginResetModel/endResetModel for simplicity.
        Differential updates (insertRows, removeRows, dataChanged) are a future optimization.
        """
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def get_entity_at(self, row: int) -> Any:
        """Returns the domain entity at the specified row."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def get_entity_id_at(self, row: int) -> Any:
        """Helper to get the ID of an entity at a row."""
        entity = self.get_entity_at(row)
        if entity:
            return getattr(entity, 'id', None)
        return None
