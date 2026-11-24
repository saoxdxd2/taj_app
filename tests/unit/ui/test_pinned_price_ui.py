"""UI surfaces use effective prices and the pinned-price service action."""
import os
from decimal import Decimal

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QInputDialog  # noqa: E402

from src.modules.inventory.models import Product, ProductState  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _product(product_id, sku, *, sale_price, pin=None,
             state=ProductState.DRAFT):
    product = Product(
        name=f"Name {sku}", sku=sku, sale_price=Decimal(sale_price),
        purchase_price=Decimal("0.00"), vat_rate=Decimal("20.00"),
        pinned_price=pin, state=state,
    )
    product.id = product_id
    return product


def test_product_table_shows_pinned_and_priced_columns(qapp):
    from src.ui.models.product_model import ProductTableModel

    model = ProductTableModel()
    product = _product(1, "UI-PIN", sale_price="0.00", pin=Decimal("149.00"))
    model.update_data([product])

    assert model.columnCount() == 9
    assert model.headerData(7, Qt.Horizontal) == "Pinned Price"
    assert model.headerData(8, Qt.Horizontal) == "Priced"
    assert model.data(model.index(0, 7)) == "149.00"
    assert model.data(model.index(0, 8)) == "Yes"

    product.pinned_price = None
    assert model.data(model.index(0, 7)) == ""
    assert model.data(model.index(0, 8)) == "No"


def test_invoice_item_dialog_prefills_effective_price(qapp, monkeypatch):
    from src.ui.dialogs import sales_dialogs

    products = [
        _product(1, "UI-PINNED", sale_price="0.00",
                 pin=Decimal("149.00"), state=ProductState.ACTIVE),
        _product(2, "UI-UNPRICED", sale_price="0.00",
                 state=ProductState.ACTIVE),
    ]
    monkeypatch.setattr(
        sales_dialogs.InventoryService, "get_all_products",
        lambda **kwargs: products,
    )

    dialog = sales_dialogs.InvoiceAddItemDialog(context=object())

    # Unpriced products must not appear in the POS picker.
    assert dialog.product_combo.count() == 1
    assert dialog.product_combo.currentData() == 1
    assert dialog.unit_price_input.value() == pytest.approx(149.00)


@pytest.mark.parametrize("entered,expected", [("149.00", "149.00"), ("", "")])
def test_product_widget_pin_action_calls_service(
    qapp, monkeypatch, entered, expected,
):
    from src.ui.widgets import product_widget as module

    calls = []
    monkeypatch.setattr(module.ProductWidget, "refresh_table", lambda self: None)
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *args, **kwargs: (entered, True)),
    )
    monkeypatch.setattr(
        module.InventoryService, "set_pinned_price",
        staticmethod(lambda *args, **kwargs: calls.append((args, kwargs))),
    )

    widget = module.ProductWidget()
    widget.table_model.update_data([
        _product(7, "UI-ACTION", sale_price="0.00")
    ])
    widget.table.selectRow(0)

    widget.on_set_pinned_price()

    assert widget.btn_pin_price is not None
    assert len(calls) == 1
    assert calls[0][1]["product_id"] == 7
    assert calls[0][1]["pinned_price"] == expected
