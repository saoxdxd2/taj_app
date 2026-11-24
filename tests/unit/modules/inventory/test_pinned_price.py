"""Pinned price model, schema and InventoryService setter coverage."""
from decimal import Decimal

import pytest
from sqlalchemy import Numeric, inspect

from src.modules.audit.models import AuditEvent
from src.modules.inventory.models import (
    Product, ProductState, as_decimal, pinned_price_value,
)
from src.modules.inventory.services import InventoryService
from src.security.permissions import AccessDenied


def _make_product(session, sku, *, sale_price="0.00", pin=None,
                  state=ProductState.DRAFT):
    product = Product(
        name=f"Product {sku}", sku=sku, sale_price=Decimal(sale_price),
        purchase_price=Decimal("0.00"), vat_rate=Decimal("20.00"),
        pinned_price=pin, state=state,
    )
    session.add(product)
    session.flush()
    return product


def _update_events(session, product):
    return (
        session.query(AuditEvent)
        .filter(
            AuditEvent.entity_name == "Product",
            AuditEvent.entity_id == str(product.id),
            AuditEvent.action == "UPDATE",
        )
        .order_by(AuditEvent.id)
        .all()
    )


def test_pinned_price_column_matches_contract(db_engine):
    columns = {c["name"]: c for c in inspect(db_engine).get_columns("product")}
    pinned = columns["pinned_price"]
    assert isinstance(pinned["type"], Numeric)
    assert (pinned["type"].precision, pinned["type"].scale) == (12, 2)
    assert pinned["nullable"] is True


def test_model_helpers_use_pin_then_base_price():
    product = Product(sale_price="0.00", pinned_price="149.50")
    assert product.effective_price == Decimal("149.50")
    assert product.priced is True

    product.pinned_price = None
    product.sale_price = "79.90"
    assert product.effective_price == Decimal("79.90")
    assert product.priced is True

    product.sale_price = 0
    assert product.effective_price == Decimal("0")
    assert product.priced is False

    # Defensive parsing: floats, blanks and malformed values never raise.
    product.pinned_price = 12.5
    assert pinned_price_value(product.pinned_price) == Decimal("12.5")
    product.pinned_price = ""
    assert as_decimal(product.pinned_price) is None
    assert product.effective_price == Decimal("0")


def test_set_pinned_price_activates_draft_and_audits_once(session, admin_context):
    product = _make_product(session, "PIN-SET")
    assert product.state == ProductState.DRAFT

    updated = InventoryService.set_pinned_price(
        admin_context, session, product.id, "149.00"
    )

    assert updated is product
    assert updated.pinned_price == Decimal("149.00")
    assert updated.state == ProductState.ACTIVE
    assert updated.effective_price == Decimal("149.00")
    assert updated.priced is True
    events = _update_events(session, product)
    assert len(events) == 1
    assert events[0].after_values["pinned_price"] == "149.00"
    assert events[0].after_values["state"] == "Active"


def test_set_pinned_price_clear_never_changes_state(session, admin_context):
    draft = _make_product(session, "PIN-DRAFT", pin=Decimal("50.00"))
    InventoryService.set_pinned_price(admin_context, session, draft.id, "")
    assert draft.pinned_price is None
    assert draft.state == ProductState.DRAFT

    active = _make_product(session, "PIN-ACTIVE", pin=Decimal("50.00"),
                           state=ProductState.ACTIVE)
    InventoryService.set_pinned_price(admin_context, session, active.id, 0)
    assert active.pinned_price is None
    assert active.state == ProductState.ACTIVE
    assert active.effective_price == Decimal("0")
    assert active.priced is False
    # One UPDATE event per real change, not one per field assignment.
    assert len(_update_events(session, draft)) == 1
    assert len(_update_events(session, active)) == 1


@pytest.mark.parametrize("value", ["not-a-price", "-5.00", "NaN", None])
def test_set_pinned_price_invalid_values_clear(session, admin_context, value):
    product = _make_product(session, "PIN-CLEAR", pin=Decimal("50.00"),
                            state=ProductState.ACTIVE)
    InventoryService.set_pinned_price(admin_context, session, product.id, value)
    assert product.pinned_price is None
    assert product.state == ProductState.ACTIVE


def test_set_pinned_price_quantizes_to_money(session, admin_context):
    product = _make_product(session, "PIN-FLOAT")
    InventoryService.set_pinned_price(admin_context, session, product.id, 12.345)
    assert product.pinned_price == Decimal("12.35")


def test_set_pinned_price_missing_product_returns_none(session, admin_context):
    assert InventoryService.set_pinned_price(
        admin_context, session, 999999, "10.00"
    ) is None


def test_set_pinned_price_requires_permission(session, unauthorized_context):
    product = _make_product(session, "PIN-AUTH")
    with pytest.raises(AccessDenied):
        InventoryService.set_pinned_price(
            unauthorized_context, session, product.id, "10.00"
        )
    assert product.pinned_price is None
