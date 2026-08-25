import pytest
from decimal import Decimal

from src.modules.inventory.services import InventoryService
from src.modules.inventory.models import AttributeDef, AttributeDataType, ProductAttribute, StockLevel
from src.core.context import RequestContext
from src.security.permissions import AccessDenied


@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})


@pytest.fixture
def unauthorized_context():
    return RequestContext(user_id="2", username="guest", role="Guest", permissions=set())


@pytest.fixture
def product(session, admin_context):
    p = InventoryService.create_product(
        context=admin_context, session=session,
        name="Clim LG 12000 BTU", sku="LG-AC12K",
        purchase_price=Decimal("4000.00"), sale_price=Decimal("5300.00"),
    )
    InventoryService.activate_product(context=admin_context, session=session, product_id=p.id)
    return p


# --- Attribute definitions ---

def test_create_attribute_def(session, admin_context):
    """User-defined attributes: key normalized, unit optional."""
    attr = InventoryService.create_attribute_def(
        context=admin_context, session=session,
        key="BTU", label="BTU", data_type="Number", unit="BTU",
    )
    assert attr.key == "btu"  # normalized
    assert attr.data_type == AttributeDataType.NUMBER
    assert attr.unit == "BTU"


def test_create_duplicate_attribute_rejected(session, admin_context):
    InventoryService.create_attribute_def(
        context=admin_context, session=session, key="btu", label="BTU",
    )
    with pytest.raises(ValueError, match="already exists"):
        InventoryService.create_attribute_def(
            context=admin_context, session=session, key="btu", label="BTU",
        )


def test_attribute_requires_authorization(session, unauthorized_context):
    with pytest.raises(AccessDenied):
        InventoryService.create_attribute_def(
            context=unauthorized_context, session=session, key="x", label="X",
        )


# --- Product attribute values ---

def test_set_and_get_product_attribute(session, admin_context, product):
    attr = InventoryService.create_attribute_def(
        context=admin_context, session=session,
        key="btu", label="BTU", data_type="Number", unit="BTU",
    )
    InventoryService.set_product_attribute(
        context=admin_context, session=session,
        product_id=product.id, attribute_def_id=attr.id, value_text="12000",
    )
    # Update the same attribute (no duplicate row)
    InventoryService.set_product_attribute(
        context=admin_context, session=session,
        product_id=product.id, attribute_def_id=attr.id, value_text="9000",
    )
    values = InventoryService.get_product_attributes(
        context=admin_context, session=session, product_id=product.id,
    )
    assert len(values) == 1
    assert values[0]["key"] == "btu"
    assert values[0]["value"] == "9000"
    assert values[0]["unit"] == "BTU"


def test_number_attribute_rejects_non_numeric(session, admin_context, product):
    attr = InventoryService.create_attribute_def(
        context=admin_context, session=session,
        key="btu", label="BTU", data_type="Number",
    )
    with pytest.raises(ValueError, match="expects a number"):
        InventoryService.set_product_attribute(
            context=admin_context, session=session,
            product_id=product.id, attribute_def_id=attr.id, value_text="loud",
        )


def test_cannot_delete_attribute_in_use(session, admin_context, product):
    """Attributes used by products are protected from deletion."""
    attr = InventoryService.create_attribute_def(
        context=admin_context, session=session, key="btu", label="BTU",
    )
    InventoryService.set_product_attribute(
        context=admin_context, session=session,
        product_id=product.id, attribute_def_id=attr.id, value_text="12000",
    )
    with pytest.raises(ValueError, match="still use it"):
        InventoryService.delete_attribute_def(
            context=admin_context, session=session, attribute_def_id=attr.id,
        )


def test_delete_unused_attribute_ok(session, admin_context):
    attr = InventoryService.create_attribute_def(
        context=admin_context, session=session, key="unused", label="Unused",
    )
    assert InventoryService.delete_attribute_def(
        context=admin_context, session=session, attribute_def_id=attr.id,
    )


# --- Min stock / reorder view ---

def test_low_stock_view(session, admin_context):
    """Products at/below their threshold appear with the shortfall."""
    low = InventoryService.create_product(
        context=admin_context, session=session,
        name="Low Stock Item", sku="LOW-01",
        purchase_price=Decimal("10.00"), sale_price=Decimal("20.00"),
    )
    ok = InventoryService.create_product(
        context=admin_context, session=session,
        name="Healthy Stock Item", sku="OK-01",
        purchase_price=Decimal("10.00"), sale_price=Decimal("20.00"),
    )
    for p in (low, ok):
        InventoryService.activate_product(context=admin_context, session=session, product_id=p.id)
        InventoryService.adjust_stock(
            context=admin_context, session=session, product_id=p.id,
            quantity_change=10, movement_type="Purchase", reference=f"INIT-{p.sku}",
        )
    InventoryService.set_min_quantity(context=admin_context, session=session, product_id=low.id, min_quantity=8)
    InventoryService.set_min_quantity(context=admin_context, session=session, product_id=ok.id, min_quantity=2)

    # quantity 10 > min 8 -> NOT low stock yet
    low_stock = InventoryService.get_low_stock_products(context=admin_context, session=session)
    skus = [item["sku"] for item in low_stock]
    assert "LOW-01" not in skus
    assert "OK-01" not in skus

    # Sell 3 units of LOW-01 -> quantity 7 <= 8 -> now low with shortfall 1
    InventoryService.adjust_stock(
        context=admin_context, session=session, product_id=low.id,
        quantity_change=-3, movement_type="Sale", reference="TEST-SALE",
    )
    low_stock = InventoryService.get_low_stock_products(context=admin_context, session=session)
    entry = next(item for item in low_stock if item["sku"] == "LOW-01")
    assert entry["quantity"] == 7
    assert entry["min_quantity"] == 8
    assert entry["shortfall"] == 1