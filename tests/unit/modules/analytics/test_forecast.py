import uuid

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.modules.analytics.services import ForecastService
from src.modules.inventory.services import InventoryService
from src.modules.sales.services import SalesService
from src.modules.crm.models import Customer
from src.core.context import RequestContext


@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})


@pytest.fixture
def customer(session):
    c = Customer(company_name="Forecast Client")
    session.add(c)
    session.flush()
    return c


def _tracked_product(session, admin_context, sku=None, min_quantity=5):
    """Active product with a reorder threshold."""
    if sku is None:
        sku = f"FCT-{uuid.uuid4().hex[:8]}"
    product = InventoryService.create_product(
        context=admin_context, session=session,
        name=f"Unit {sku}", sku=sku,
        purchase_price=Decimal("100"), sale_price=Decimal("150"),
    )
    InventoryService.activate_product(context=admin_context, session=session, product_id=product.id)
    # set threshold via stock level
    from src.modules.inventory.models import StockLevel
    stock = session.query(StockLevel).filter(StockLevel.product_id == product.id).first()
    if not stock:
        stock = StockLevel(product_id=product.id, quantity=0, min_quantity=min_quantity)
        session.add(stock)
        session.flush()
    else:
        stock.min_quantity = min_quantity
        session.flush()
    return product


def _sell(session, admin_context, customer, product, qty):
    invoice = SalesService.create_invoice_draft(
        context=admin_context, session=session, customer_id=customer.id,
    )
    SalesService.add_item_to_invoice(
        context=admin_context, session=session, invoice_id=invoice.id,
        product_id=product.id, quantity=qty,
        unit_price=Decimal("150"), vat_rate=Decimal("20"),
        unit_cost=Decimal("100"),
    )
    SalesService.validate_invoice(context=admin_context, session=session, invoice_id=invoice.id)


def test_forecast_suggests_based_on_velocity(session, admin_context, customer):
    """Sold 35 in 90 days, 5 left in stock -> need ceil(35/90*30)=12, suggest 12-5=7."""
    product = _tracked_product(session, admin_context, min_quantity=5)
    InventoryService.adjust_stock(
        context=admin_context, session=session, product_id=product.id,
        quantity_change=40, movement_type="Purchase", reference="INIT",
    )
    _sell(session, admin_context, customer, product, qty=35)

    suggestions = ForecastService.get_reorder_suggestions(
        context=admin_context, session=session,
        lookback_days=90, horizon_days=30,
    )
    entry = next(s for s in suggestions if s["sku"] == product.sku)
    assert entry["sold_in_window"] == 35
    assert entry["stock"] == 5                  # 40 bought - 35 sold
    assert entry["horizon_need"] == 12          # ceil(35/90*30) = ceil(11.67)
    assert entry["suggested_qty"] == 7          # max(12-5, 5-5)


def test_forecast_ignores_untracked_products(session, admin_context, customer):
    """Products without a reorder threshold never appear."""
    sku = f"NOTRK-{uuid.uuid4().hex[:6]}"
    product = InventoryService.create_product(
        context=admin_context, session=session,
        name="Untracked", sku=sku,
        purchase_price=Decimal("100"), sale_price=Decimal("150"),
    )
    InventoryService.activate_product(context=admin_context, session=session, product_id=product.id)

    suggestions = ForecastService.get_reorder_suggestions(context=admin_context, session=session)
    assert all(s["sku"] != sku for s in suggestions)


def test_forecast_no_suggestion_when_covered(session, admin_context, customer):
    """Plenty of stock and no sales -> no suggestion."""
    product = _tracked_product(session, admin_context, min_quantity=2)
    InventoryService.adjust_stock(
        context=admin_context, session=session, product_id=product.id,
        quantity_change=50, movement_type="Purchase", reference="INIT",
    )

    suggestions = ForecastService.get_reorder_suggestions(context=admin_context, session=session)
    assert all(s["sku"] != product.sku for s in suggestions)


def test_forecast_validates_params(session, admin_context):
    with pytest.raises(ValueError, match="positive"):
        ForecastService.get_reorder_suggestions(context=admin_context, session=session,
                                                lookback_days=0)