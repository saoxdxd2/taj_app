"""Review dialog for a scanned supplier invoice.

OCR only proposes. Nothing reaches the database until the user confirms this
dialog, and even then the result is a Draft purchase: validation (stock and
journal entries) remains a separate, deliberate action.
"""

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
)

from src.modules.inventory.services import InventoryService
from src.modules.purchasing.ocr import load_page_image
from src.modules.suppliers.services import SupplierService
from src.ui.dialogs.base_dialog import FormDialog, MUTED
from src.ui.layout import add_elided_columns

COLUMNS = ["Product", "Reference", "Description", "Qty", "Unit cost", "Amount"]
QTY_COL, COST_COL, AMOUNT_COL = 3, 4, 5


class InvoiceImportDialog(FormDialog):
    def __init__(self, context, scan, parent=None):
        self.context = context
        self.scan = scan
        self.invoice = scan.invoice
        self._assignments = {}
        self._loading_combo = False

        self.suppliers = [
            row for row in SupplierService.get_all_suppliers(context, limit=2000)
            if not row.is_archived
        ]
        self.products = [
            row for row in InventoryService.get_all_products(context, limit=2000)
            if row.state.value != "Archived"
        ]

        super().__init__(
            title="Review Supplier Invoice",
            subtitle="Check every value against the paper. Saving creates a Draft purchase; "
                     "stock and accounting change only when you validate it.",
            min_width=960,
            parent=parent,
        )
        self.setMinimumHeight(680)
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        top = QHBoxLayout()
        top.setSpacing(18)

        preview = QLabel()
        preview.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        preview.setStyleSheet("border: 1px solid #cbd5e0; background: #f7fafc;")
        self._fill_preview(preview)
        top.addWidget(preview)

        form = QFormLayout()
        form.setSpacing(8)

        self.supplier_combo = QComboBox()
        self.supplier_combo.addItem("Select a supplier...", userData=None)
        for supplier in self.suppliers:
            self.supplier_combo.addItem(supplier.company_name, userData=supplier.id)
        if self.scan.supplier_id is not None:
            index = self.supplier_combo.findData(self.scan.supplier_id)
            if index >= 0:
                self.supplier_combo.setCurrentIndex(index)

        self.invoice_no_input = QLineEdit(self.invoice.invoice_number)
        self.invoice_no_input.setPlaceholderText("e.g. FA26003036")

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        extracted = self.invoice.invoice_date
        self.date_input.setDate(
            QDate(extracted.year, extracted.month, extracted.day)
            if extracted else QDate.currentDate()
        )

        self.reference_input = QLineEdit(self._default_reference())
        self.reference_input.setPlaceholderText("Reference of the purchase in this app")

        self.remember_check = QCheckBox("Remember this paper layout for this supplier")
        self.remember_check.setChecked(True)

        form.addRow("Supplier *", self.supplier_combo)
        form.addRow("Invoice no.", self.invoice_no_input)
        form.addRow("Invoice date", self.date_input)
        form.addRow("Purchase ref. *", self.reference_input)
        form.addRow("", self.remember_check)
        if self.scan.profile_id:
            saved = QLabel("A layout remembered from an earlier invoice was applied.")
            saved.setWordWrap(True)
            saved.setStyleSheet(f"color: {MUTED};")
            form.addRow("", saved)

        top.addLayout(form, 1)
        self._root.addLayout(top)

        self.table = QTableWidget(len(self.scan.lines), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setTextElideMode(Qt.ElideRight)
        add_elided_columns(self.table, stretch_column=2)
        self._fill_table()
        self.table.cellChanged.connect(self._cell_changed)
        self._root.addWidget(self.table, 1)

        product_row = QHBoxLayout()
        product_row.addWidget(QLabel("Product for the selected line:"))
        self.product_combo = QComboBox()
        self.product_combo.addItem("(not mapped)", userData=None)
        for product in self.products:
            self.product_combo.addItem(f"[{product.sku}] {product.name}", userData=product.id)
        self.product_combo.currentIndexChanged.connect(self._assign_product)
        product_row.addWidget(self.product_combo, 1)
        self._root.addLayout(product_row)

        self.table.itemSelectionChanged.connect(self._show_row_product)
        self.table.selectRow(0)

        self.totals_label = QLabel()
        self.totals_label.setTextFormat(Qt.RichText)
        self.totals_label.setWordWrap(True)
        self._root.addWidget(self.totals_label)

        if self.invoice.warnings:
            warnings = QLabel("⚠ " + " ".join(self.invoice.warnings))
            warnings.setWordWrap(True)
            warnings.setStyleSheet("color: #c0392b;")
            self._root.addWidget(warnings)

        box = self.add_buttons(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, ok_text="Create Draft"
        )
        box.accepted.disconnect()
        box.accepted.connect(self.validate_and_accept)

        self._refresh_totals()

    def _fill_preview(self, label):
        try:
            image = load_page_image(self.scan.file_path)
            data = image.tobytes("raw", "RGB")
            qimage = QImage(data, image.width, image.height, image.width * 3,
                            QImage.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(qimage).scaled(
                290, 420, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            label.setPixmap(pixmap)
        except Exception:  # noqa: BLE001 - the paper preview is only a convenience
            label.setText("Page preview unavailable")

    def _fill_table(self):
        self.table.blockSignals(True)
        for row, line in enumerate(self.scan.lines):
            self._assignments[row] = line.product_id
            product = QTableWidgetItem(line.product_label or "(not mapped)")
            product.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 0, product)

            for column, text in ((1, line.reference), (2, line.label)):
                item = QTableWidgetItem(text)
                self.table.setItem(row, column, item)

            quantity = QTableWidgetItem(str(line.quantity))
            quantity.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, QTY_COL, quantity)

            cost = QTableWidgetItem(f"{line.unit_cost:.2f}")
            cost.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, COST_COL, cost)

            amount = QTableWidgetItem(f"{line.amount:.2f}")
            amount.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            amount.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, AMOUNT_COL, amount)
        self.table.blockSignals(False)

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def _selected_row(self):
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _show_row_product(self):
        row = self._selected_row()
        if row < 0:
            return
        self._loading_combo = True
        index = self.product_combo.findData(self._assignments.get(row))
        self.product_combo.setCurrentIndex(max(index, 0))
        self._loading_combo = False

    def _assign_product(self):
        if self._loading_combo:
            return
        row = self._selected_row()
        if row < 0:
            return
        product_id = self.product_combo.currentData()
        self._assignments[row] = product_id
        item = self.table.item(row, 0)
        if item is not None:
            item.setText(self.product_combo.currentText() if product_id else "(not mapped)")

    def _cell_changed(self, row, column):
        if column not in (QTY_COL, COST_COL):
            return
        quantity = self._quantity(row)
        cost = self._cost(row)
        if quantity is None or cost is None:
            return
        amount = self.table.item(row, AMOUNT_COL)
        if amount is not None:
            self.table.blockSignals(True)
            amount.setText(f"{quantity * cost:.2f}")
            self.table.blockSignals(False)
        self._refresh_totals()

    def _quantity(self, row):
        item = self.table.item(row, QTY_COL)
        try:
            value = int((item.text() if item else "").strip())
        except ValueError:
            return None
        return value if value > 0 else None

    def _cost(self, row):
        item = self.table.item(row, COST_COL)
        raw = (item.text() if item else "").replace(" ", "").replace(",", ".")
        try:
            value = Decimal(raw)
        except InvalidOperation:
            return None
        return value if value >= 0 else None

    def _line_total(self):
        total = Decimal("0.00")
        for row in range(self.table.rowCount()):
            item = self.table.item(row, AMOUNT_COL)
            try:
                total += Decimal((item.text() if item else "0").replace(",", "."))
            except InvalidOperation:
                pass
        return total

    def _refresh_totals(self):
        total = self._line_total()
        parts = [f"<b>Lines total:</b> {total:,.2f} DH"]
        if self.invoice.total_ht is not None:
            parts.append(f"Paper HT: {self.invoice.total_ht:,.2f}")
        if self.invoice.total_tva is not None:
            parts.append(f"TVA: {self.invoice.total_tva:,.2f}")
        if self.invoice.total_ttc is not None:
            parts.append(f"TTC: {self.invoice.total_ttc:,.2f}")
        if self.invoice.total_ht is not None:
            difference = self.invoice.total_ht - total
            if abs(difference) > Decimal("0.05"):
                parts.append(
                    f"<span style='color:#c0392b;'>Lines differ from the paper HT "
                    f"by {difference:,.2f} DH</span>"
                )
        else:
            parts.append(
                "<span style='color:#c0392b;'>Paper totals were not read — "
                "check the amounts on the paper.</span>"
            )
        self.totals_label.setText(" &nbsp;|&nbsp; ".join(parts))
        self.totals_label.setStyleSheet(f"color: {MUTED};")

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def _default_reference(self):
        number = (self.invoice.invoice_number or "").strip()
        if number:
            return f"PUR-{number}"[:50]
        return "SCAN-" + QDate.currentDate().toString("yyyyMMdd")

    def validate_and_accept(self):
        if self.supplier_combo.currentData() is None:
            QMessageBox.warning(self, "Supplier required",
                                "Select the supplier this paper belongs to.")
            return
        if not self.reference_input.text().strip():
            QMessageBox.warning(self, "Reference required",
                                "Give this purchase a reference.")
            return

        for row in range(self.table.rowCount()):
            if not self._assignments.get(row):
                self.table.selectRow(row)
                QMessageBox.warning(
                    self, "Product required",
                    f"Line {row + 1} is not mapped to an inventory product. "
                    "Pick one in 'Product for the selected line'.",
                )
                return
            if self._quantity(row) is None:
                self.table.selectRow(row)
                QMessageBox.warning(self, "Quantity", f"Line {row + 1} needs a positive quantity.")
                return
            if self._cost(row) is None:
                self.table.selectRow(row)
                QMessageBox.warning(self, "Unit cost", f"Line {row + 1} needs a valid unit cost.")
                return

        total = self._line_total()
        paper = self.invoice.total_ht
        if paper is not None and abs(paper - total) > Decimal("0.05"):
            answer = QMessageBox.question(
                self, "Totals do not match",
                f"The lines total {total:,.2f} DH but the paper shows {paper:,.2f} DH HT.\n\n"
                "Save this draft anyway?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.accept()

    def get_data(self):
        items = []
        for row in range(self.table.rowCount()):
            items.append({
                "product_id": self._assignments.get(row),
                "quantity": self._quantity(row),
                "unit_cost": self._cost(row),
                "reference": self.table.item(row, 1).text().strip(),
                "label": self.table.item(row, 2).text().strip(),
            })
        selected = self.date_input.date()
        return {
            "file_path": self.scan.file_path,
            "file_hash": self.scan.file_hash,
            "fingerprint": self.invoice.fingerprint,
            "supplier_id": self.supplier_combo.currentData(),
            "reference": self.reference_input.text().strip(),
            "invoice_no": self.invoice_no_input.text().strip() or None,
            "invoice_date": selected.toPython(),
            "items": items,
            "columns": self.invoice.columns,
            "remember_format": self.remember_check.isChecked(),
        }
