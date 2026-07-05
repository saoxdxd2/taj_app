from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal, Qt

class PaginationWidget(QWidget):
    page_changed = Signal(int, int) # emits (limit, offset)

    def __init__(self, limit=100, parent=None):
        super().__init__(parent)
        self.limit = limit
        self.offset = 0
        self.total_count = 0
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_prev = QPushButton("< Previous")
        self.btn_prev.clicked.connect(self.prev_page)
        
        self.lbl_status = QLabel("Showing 0-0 of 0")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        
        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self.next_page)

        layout.addStretch()
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.btn_next)
        layout.addStretch()

        self.update_buttons()

    def update_state(self, total_count: int):
        self.total_count = total_count
        # Prevent offset from exceeding bounds if data was deleted
        if self.offset >= self.total_count and self.total_count > 0:
            self.offset = max(0, self.total_count - self.limit)
            
        start = self.offset + 1 if self.total_count > 0 else 0
        end = min(self.offset + self.limit, self.total_count)
        self.lbl_status.setText(f"Showing {start}-{end} of {self.total_count}")
        self.update_buttons()

    def update_buttons(self):
        self.btn_prev.setEnabled(self.offset > 0)
        self.btn_next.setEnabled(self.offset + self.limit < self.total_count)

    def next_page(self):
        if self.offset + self.limit < self.total_count:
            self.offset += self.limit
            self.page_changed.emit(self.limit, self.offset)

    def prev_page(self):
        if self.offset > 0:
            self.offset = max(0, self.offset - self.limit)
            self.page_changed.emit(self.limit, self.offset)
            
    def reset(self):
        self.offset = 0
        self.page_changed.emit(self.limit, self.offset)
