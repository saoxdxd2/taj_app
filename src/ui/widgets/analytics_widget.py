"""
Analytics & Charts page.

Visualizations powered by QtCharts (bundled with PySide6, no extra
dependency):
- Monthly Revenue / Cost / Gross Margin bar chart (per year)
- Cash-flow breakdown pie chart (current month)
- Top debtors table
"""
from datetime import datetime

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QSpinBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCharts import (QChartView, QChart, QBarSeries, QBarSet,
                              QBarCategoryAxis, QValueAxis, QPieSeries)

from src.core.session import CurrentSession
from src.modules.finance.services import FinanceService

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ACCENT = "#e67e22"
SIDEBAR_BG = "#1f3a5f"
MUTED = "#718096"


class AnalyticsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = CurrentSession.get_context()
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header + year selector
        header_row = QHBoxLayout()
        title = QLabel(
            f"<h2 style='color:{SIDEBAR_BG};'>Analytics</h2>"
            f"<span style='color:{MUTED};'>Profit per month and where the money goes.</span>"
        )
        title.setTextFormat(Qt.RichText)
        header_row.addWidget(title)
        header_row.addStretch()

        header_row.addWidget(QLabel("Year:"))
        self.year_input = QSpinBox()
        self.year_input.setRange(2000, 2100)
        self.year_input.setValue(datetime.now().year)
        header_row.addWidget(self.year_input)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # Charts row: bars (profit) + pie (cash flow)
        charts_row = QHBoxLayout()
        charts_row.setSpacing(16)

        self.profit_chart_view = QChartView()
        self.profit_chart_view.setRenderHint(QPainter.Antialiasing)
        charts_row.addWidget(self.profit_chart_view, stretch=3)

        self.cashflow_chart_view = QChartView()
        self.cashflow_chart_view.setRenderHint(QPainter.Antialiasing)
        charts_row.addWidget(self.cashflow_chart_view, stretch=2)

        layout.addLayout(charts_row, stretch=5)

        # Debtors table
        debtors_label = QLabel(f"<b style='color:{SIDEBAR_BG};'>Clients who owe money</b>")
        debtors_label.setTextFormat(Qt.RichText)
        layout.addWidget(debtors_label)

        self.debtors_table = QTableWidget(0, 4)
        self.debtors_table.setHorizontalHeaderLabels(
            ["Client", "Invoiced (DH)", "Paid (DH)", "Outstanding (DH)"]
        )
        self.debtors_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.debtors_table.verticalHeader().setVisible(False)
        self.debtors_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.debtors_table, stretch=2)

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def refresh(self):
        self._load_profit_chart()
        self._load_cashflow_pie()
        self._load_debtors()

    def _load_profit_chart(self):
        chart = QChart()
        chart.setTitle(f"Revenue vs Cost vs Margin — {self.year_input.value()} (DH)")
        chart.legend().setAlignment(Qt.AlignBottom)

        try:
            series_data = FinanceService.get_monthly_profit_series(
                context=self.context, year=self.year_input.value()
            )
        except Exception as e:
            chart.setTitle(f"Could not load profit data: {e}")
            self.profit_chart_view.setChart(chart)
            return

        revenue_set = QBarSet("Revenue (excl. VAT)")
        cost_set = QBarSet("Cost")
        margin_set = QBarSet("Gross Margin")
        revenue_set.setColor(QColor("#1f3a5f"))
        cost_set.setColor(QColor("#c0392b"))
        margin_set.setColor(QColor(ACCENT))

        for m in series_data:
            revenue_set.append(float(m["revenue_excl_vat"]))
            cost_set.append(float(m["total_cost"]))
            margin_set.append(float(m["gross_margin"]))

        series = QBarSeries()
        series.append(revenue_set)
        series.append(cost_set)
        series.append(margin_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(MONTH_LABELS)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelFormat("%.0f")
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        self.profit_chart_view.setChart(chart)

    def _load_cashflow_pie(self):
        chart = QChart()
        chart.setTitle("Money in / out — this month")

        try:
            flow = FinanceService.get_cash_flow(context=self.context)
        except Exception as e:
            chart.setTitle(f"Could not load cash flow: {e}")
            self.cashflow_chart_view.setChart(chart)
            return

        series = QPieSeries()
        palette = [QColor("#27ae60"), QColor("#c0392b"), QColor(ACCENT),
                   QColor(SIDEBAR_BG), QColor("#8e44ad"), QColor("#16a085")]
        i = 0
        for label, amount in flow["breakdown"].items():
            value = float(amount)
            if abs(value) < 0.005:
                continue
            slice_ = series.append(f"{label} ({value:,.0f})", abs(value))
            slice_.setColor(palette[i % len(palette)])
            i += 1

        if series.count() == 0:
            series.append("No movements yet", 1.0)
            series.slices()[0].setColor(QColor("#dfe6ec"))

        series.setLabelsVisible(True)
        chart.addSeries(series)
        chart.legend().setAlignment(Qt.AlignRight)
        self.cashflow_chart_view.setChart(chart)

    def _load_debtors(self):
        try:
            debtors = FinanceService.get_debtors(context=self.context)
        except Exception as e:
            self.debtors_table.setRowCount(1)
            self.debtors_table.setItem(0, 0, QTableWidgetItem(f"Error: {e}"))
            return

        self.debtors_table.setRowCount(len(debtors))
        for row, d in enumerate(debtors):
            values = [
                d["company_name"],
                f"{float(d['total_invoiced']):,.2f}",
                f"{float(d['total_paid']):,.2f}",
                f"{float(d['outstanding']):,.2f}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 3:
                    item.setForeground(QColor("#c0392b"))
                self.debtors_table.setItem(row, col, item)