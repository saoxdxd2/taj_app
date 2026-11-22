"""
Analytics page, split into two tabs:

- Profit & Stock: period profit (sales, cost, expenses) and the stock
  value at both ends of the period, with CSV export.
- Charts: monthly profit bars, cash-flow pie and the debtor list.
"""
import csv
from datetime import datetime, time, timedelta

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QSpinBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QDateEdit,
                               QGroupBox, QGridLayout, QFileDialog,
                               QMessageBox)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCharts import (QChartView, QChart, QBarSeries, QBarSet,
                              QBarCategoryAxis, QValueAxis, QPieSeries)

from src.core.session import CurrentSession
from src.modules.finance.services import FinanceService
from src.modules.reports.services import ReportsService
from src.security.permissions import AccessDenied
from src.ui.layout import add_elided_columns, scaled, size_table_height

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ACCENT = "#e67e22"
SIDEBAR_BG = "#1f3a5f"
MUTED = "#718096"
GREEN = "#27ae60"
RED = "#c0392b"


def _money(value) -> str:
    return f"{value:,.2f} DH"


class AnalyticsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = CurrentSession.get_context()
        self._report_rows: list[tuple[str, str]] = []
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel(
            f"<h2 style='color:{SIDEBAR_BG};'>Analytics</h2>"
            f"<span style='color:{MUTED};'>Profit, stock value and charts.</span>"
        )
        title.setTextFormat(Qt.RichText)
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_report_tab(), "Profit && Stock")
        self.tabs.addTab(self._build_charts_tab(), "Charts")
        layout.addWidget(self.tabs, 1)

    # ------------------------------------------------------------------
    # Profit & stock tab
    # ------------------------------------------------------------------

    def _build_report_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("From:"))
        first_of_month = QDate.currentDate().addDays(1 - QDate.currentDate().day())
        self.from_input = QDateEdit(first_of_month)
        self.from_input.setCalendarPopup(True)
        self.from_input.setDisplayFormat("dd/MM/yyyy")
        self.from_input.setMinimumWidth(scaled(130))
        controls.addWidget(self.from_input)

        controls.addWidget(QLabel("To:"))
        self.to_input = QDateEdit(QDate.currentDate())
        self.to_input.setCalendarPopup(True)
        self.to_input.setDisplayFormat("dd/MM/yyyy")
        self.to_input.setMinimumWidth(scaled(130))
        controls.addWidget(self.to_input)

        self.btn_report_refresh = QPushButton("Refresh")
        self.btn_report_refresh.clicked.connect(self._load_report)
        controls.addWidget(self.btn_report_refresh)

        self.btn_report_export = QPushButton("Export CSV")
        self.btn_report_export.clicked.connect(self.export_report)
        controls.addWidget(self.btn_report_export)
        controls.addStretch()
        layout.addLayout(controls)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.gross_value = self._add_card(cards, 0, 0, "Gross Profit")
        self.net_value = self._add_card(cards, 0, 1, "Net Profit")
        self.sales_value = self._add_card(cards, 0, 2, "Sales (excl. VAT)")
        self.opening_value = self._add_card(cards, 1, 0, "Opening Stock")
        self.closing_value = self._add_card(cards, 1, 1, "Closing Stock")
        self.expenses_value = self._add_card(cards, 1, 2, "Purchases / Expenses")
        for column in range(3):
            cards.setColumnStretch(column, 1)
        layout.addLayout(cards)

        self.report_table = QTableWidget(0, 2)
        self.report_table.setHorizontalHeaderLabels(["Line", "Amount"])
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.setEditTriggers(QTableWidget.NoEditTriggers)
        add_elided_columns(self.report_table, stretch_column=0)
        size_table_height(self.report_table, visible_rows=12)
        layout.addWidget(self.report_table, 1)
        return page

    def _add_card(self, grid: QGridLayout, row: int, col: int, caption: str):
        box = QGroupBox(caption)
        box_layout = QVBoxLayout(box)
        value = QLabel("—")
        value.setStyleSheet(f"color:{SIDEBAR_BG}; font-size: 16px; font-weight: bold;")
        box_layout.addWidget(value)
        grid.addWidget(box, row, col)
        return value

    def _period_bounds(self):
        start = datetime.combine(self.from_input.date().toPython(), time.min)
        end = datetime.combine(
            self.to_input.date().toPython() + timedelta(days=1), time.min
        )
        return start, end

    def _load_report(self):
        try:
            start, end = self._period_bounds()
            report = ReportsService.get_profit_and_stock_report(
                self.context, start=start, end=end
            )
        except AccessDenied:
            self._set_cards_placeholder("No permission")
            self.report_table.setRowCount(0)
            self._report_rows = []
            return
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to build the report: {exc}")
            return

        net = report["net_margin"]
        self.gross_value.setText(_money(report["gross_margin"]))
        self.gross_value.setStyleSheet(
            f"color:{GREEN if report['gross_margin'] >= 0 else RED};"
            " font-size: 16px; font-weight: bold;"
        )
        self.net_value.setText(_money(net))
        self.net_value.setStyleSheet(
            f"color:{GREEN if net >= 0 else RED}; font-size: 16px; font-weight: bold;"
        )
        self.sales_value.setText(_money(report["revenue_excl_vat"]))
        self.sales_value.setStyleSheet(
            f"color:{SIDEBAR_BG}; font-size: 16px; font-weight: bold;"
        )
        self.opening_value.setText(
            f"{_money(report['opening_stock_cost'])}\n"
            f"retail {_money(report['opening_stock_retail'])}"
        )
        self.closing_value.setText(
            f"{_money(report['closing_stock_cost'])}\n"
            f"retail {_money(report['closing_stock_retail'])}"
        )
        self.expenses_value.setText(
            f"purchases {_money(report['total_purchases'])}\n"
            f"expenses {_money(report['total_expenses'])}"
        )
        for label in (self.opening_value, self.closing_value, self.expenses_value):
            label.setStyleSheet(f"color:{SIDEBAR_BG}; font-size: 12px;")

        self._report_rows = [
            ("Validated invoices", str(report["invoices_count"])),
            ("Total sales (excl. VAT)", _money(report["revenue_excl_vat"])),
            ("Cost of goods sold", _money(report["cogs"])),
            ("Gross profit", _money(report["gross_margin"])),
            ("Gross margin %", f"{report['margin_percent']:.2f} %"),
            ("Total purchases (validated)", _money(report["total_purchases"])),
            ("Total expenses", _money(report["total_expenses"])),
            ("Net profit", _money(net)),
            ("Opening stock (cost)", _money(report["opening_stock_cost"])),
            ("Opening stock (retail)", _money(report["opening_stock_retail"])),
            ("Closing stock (cost)", _money(report["closing_stock_cost"])),
            ("Closing stock (retail)", _money(report["closing_stock_retail"])),
        ]
        self.report_table.setRowCount(len(self._report_rows))
        for row, (label, value) in enumerate(self._report_rows):
            self.report_table.setItem(row, 0, QTableWidgetItem(label))
            self.report_table.setItem(row, 1, QTableWidgetItem(value))

    def _set_cards_placeholder(self, text: str):
        for label in (self.gross_value, self.net_value, self.sales_value,
                      self.opening_value, self.closing_value,
                      self.expenses_value):
            label.setText(text)
            label.setStyleSheet(f"color:{MUTED}; font-size: 12px;")

    def export_report(self):
        if not self._report_rows:
            QMessageBox.information(self, "Export", "There is nothing to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Profit & Stock Report", "profit_stock_report.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            # utf-8-sig + ';' opens cleanly in French Excel.
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(["From", self.from_input.date().toString("dd/MM/yyyy")])
                writer.writerow(["To", self.to_input.date().toString("dd/MM/yyyy")])
                writer.writerow([])
                writer.writerow(["Line", "Amount"])
                writer.writerows(self._report_rows)
            QMessageBox.information(self, "Export", f"Report exported to:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    # ------------------------------------------------------------------
    # Charts tab (monthly profit, cash flow, debtors)
    # ------------------------------------------------------------------

    def _build_charts_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Year:"))
        self.year_input = QSpinBox()
        self.year_input.setRange(2000, 2100)
        self.year_input.setValue(datetime.now().year)
        header_row.addWidget(self.year_input)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        header_row.addStretch()
        layout.addLayout(header_row)

        charts_row = QHBoxLayout()
        charts_row.setSpacing(16)

        self.profit_chart_view = QChartView()
        self.profit_chart_view.setRenderHint(QPainter.Antialiasing)
        charts_row.addWidget(self.profit_chart_view, stretch=3)

        self.cashflow_chart_view = QChartView()
        self.cashflow_chart_view.setRenderHint(QPainter.Antialiasing)
        charts_row.addWidget(self.cashflow_chart_view, stretch=2)

        layout.addLayout(charts_row, stretch=5)

        debtors_label = QLabel(f"<b style='color:{SIDEBAR_BG};'>Clients who owe money</b>")
        debtors_label.setTextFormat(Qt.RichText)
        layout.addWidget(debtors_label)

        self.debtors_table = QTableWidget(0, 4)
        self.debtors_table.setHorizontalHeaderLabels(
            ["Client", "Invoiced (DH)", "Paid (DH)", "Outstanding (DH)"]
        )
        self.debtors_table.verticalHeader().setVisible(False)
        self.debtors_table.setEditTriggers(QTableWidget.NoEditTriggers)
        add_elided_columns(self.debtors_table, stretch_column=1)
        size_table_height(self.debtors_table, visible_rows=5)
        layout.addWidget(self.debtors_table, stretch=2)
        return page

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def refresh(self):
        self._load_report()
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
        revenue_set.setColor(QColor(SIDEBAR_BG))
        cost_set.setColor(QColor(RED))
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
        palette = [QColor(GREEN), QColor(RED), QColor(ACCENT),
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
                    item.setForeground(QColor(RED))
                self.debtors_table.setItem(row, col, item)
