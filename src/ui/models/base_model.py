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

    def export_to_csv(self, file_path: str):
        """
        Exports the current table view to a CSV file.
        """
        import csv
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write headers
            writer.writerow(self._headers)
            
            # Write data rows
            for row in range(self.rowCount()):
                row_data = []
                for col in range(self.columnCount()):
                    index = self.index(row, col)
                    # We rely on data() returning string representation for DisplayRole
                    data = self.data(index, Qt.DisplayRole)
                    row_data.append(str(data) if data is not None else "")
                writer.writerow(row_data)
