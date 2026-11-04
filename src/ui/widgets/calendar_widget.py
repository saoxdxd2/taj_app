from datetime import datetime, timezone

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                               QCalendarWidget, QTableWidget, QTableWidgetItem,
                               QHeaderView, QPushButton)
from PySide6.QtCore import Qt

from src.core.session import CurrentSession
from src.modules.finance.services import FinanceService
from src.security.permissions import AccessDenied
from src.ui.layout import add_elided_columns, size_table_height


class CalendarWidget(QWidget):
    """
    Month calendar with the check due-dates marked. Clicking a day shows
    the checks due that day.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = CurrentSession.get_context()
        self._due_map = {}  # date -> list of checks
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Left: the calendar
        left = QVBoxLayout()
        title = QLabel("<h2 style='color:#1f3a5f;'>Calendar</h2>"
                       "<span style='color:#718096;'>Days in orange have checks due — click a day for details.</span>")
        title.setTextFormat(Qt.RichText)
        left.addWidget(title)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar.clicked.connect(self._on_date_clicked)
        left.addWidget(self.calendar)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        left.addWidget(refresh_btn)

        layout.addLayout(left, stretch=5)

        # Right: details for the selected day
        right = QVBoxLayout()
        self.day_label = QLabel("<b>Checks due</b>")
        right.addWidget(self.day_label)

        self.checks_table = QTableWidget(0, 4)
        self.checks_table.setHorizontalHeaderLabels(
            ["Check #", "Direction", "Amount (DH)", "Party"]
        )
        self.checks_table.verticalHeader().setVisible(False)
        self.checks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        add_elided_columns(self.checks_table, stretch_column=2)
        size_table_height(self.checks_table, visible_rows=6)
        right.addWidget(self.checks_table)

        layout.addLayout(right, stretch=4)

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def refresh(self):
        """Load all pending checks and mark their due dates on the calendar."""
        from PySide6.QtGui import QTextCharFormat, QBrush, QColor
        from PySide6.QtCore import QDate
        from src.modules.finance.models import CheckStatus

        try:
            checks = FinanceService.get_all_checks(
                self.context,
                statuses=[CheckStatus.PENDING, CheckStatus.DEPOSITED],
            )
        except AccessDenied:
            self._due_map = {}
            self.day_label.setText(
                "<b>Checks are not available for your role.</b>"
            )
            self.checks_table.setRowCount(0)
            # Clear any markings left by a previous session.
            self.calendar.setDateTextFormat(QDate(), QTextCharFormat())
            return
        except Exception as e:
            self.day_label.setText(f"<b>Could not load checks:</b> {e}")
            return

        self._due_map = {}
        for c in checks:
            if c.due_date is None:
                continue
            d = c.due_date.date()
            self._due_map.setdefault(d, []).append({
                "number": c.check_number,
                "direction": c.direction.value,
                "amount": float(c.amount),
                "party": c.party_name,
            })

        # Mark dates that have pending checks. A null QDate clears every
        # special format, so removed checks disappear on refresh.
        self.calendar.setDateTextFormat(QDate(), QTextCharFormat())
        for d in self._due_map:
            f = QTextCharFormat()
            f.setForeground(QBrush(QColor("#e67e22")))
            f.setFontWeight(QTextCharFormat.Bold)
            self.calendar.setDateTextFormat(QDate(d), f)

        self._on_date_clicked(self.calendar.selectedDate())

    def _on_date_clicked(self, qdate):
        d = qdate.toPython()
        checks = self._due_map.get(d, [])
        self.day_label.setText(
            f"<b>Checks due on {d.isoformat()}</b> ({len(checks)})"
        )

        self.checks_table.setRowCount(len(checks))
        total = 0.0
        for row, c in enumerate(checks):
            values = [c["number"], c["direction"], f"{c['amount']:,.2f}", c["party"]]
            for col, value in enumerate(values):
                self.checks_table.setItem(row, col, QTableWidgetItem(str(value)))
            total += c["amount"]

        if not checks:
            self.day_label.setText(
                f"<b>No checks due on {d.isoformat()}</b>"
            )
        else:
            self.day_label.setText(
                f"<b>{len(checks)} check(s) due on {d.isoformat()} — total {total:,.2f} DH</b>"
            )
