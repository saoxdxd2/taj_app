import json
import uuid

import pytest
from decimal import Decimal

from src.modules.websync.services import WebsiteSyncService
from src.modules.inventory.services import InventoryService
from src.core.context import RequestContext


@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})


def _product(session, admin_context, sku=None, price="1999.99", activate=True):
    if sku is None:
        sku = f"WEB-{uuid.uuid4().hex[:8]}"
    product = InventoryService.create_product(
        context=admin_context, session=session,
        name=f"Split {sku}", sku=sku,
        purchase_price=Decimal("1200.00"), sale_price=Decimal(price),
    )
    if activate:
        InventoryService.activate_product(context=admin_context, session=session, product_id=product.id)
        InventoryService.adjust_stock(
            context=admin_context, session=session, product_id=product.id,
            quantity_change=7, movement_type="Purchase", reference=f"INIT-{sku}",
        )
    return product


# --- Export ---

def test_export_catalog_writes_json(tmp_path, session, admin_context):
    """Catalog JSON contains SKU, price, stock and active flag."""
    product = _product(session, admin_context)
    out = tmp_path / "catalog.json"

    result = WebsiteSyncService.export_catalog(context=admin_context, session=session,
                                               output_path=str(out))
    assert result["count"] >= 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["product_count"] == result["count"]
    entry = next(p for p in data["products"] if p["sku"] == product.sku)
    assert entry["name"] == f"Split {product.sku}"
    assert entry["sale_price"] == 1999.99
    assert entry["stock"] == 7
    assert entry["active"] is True
    assert "exported_at" in data


def test_export_catalog_excludes_archived(tmp_path, session, admin_context):
    """Archived products never reach the website."""
    product = _product(session, admin_context)
    InventoryService.archive_product(context=admin_context, session=session, product_id=product.id)
    out = tmp_path / "catalog.json"
    WebsiteSyncService.export_catalog(context=admin_context, session=session, output_path=str(out))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert all(p["sku"] != product.sku for p in data["products"])


# --- Import ---

def test_import_updates_prices_and_reports_unknowns(tmp_path, session, admin_context):
    p1 = _product(session, admin_context, price="100.00")
    p2 = _product(session, admin_context, price="200.00")

    updates = [
        {"sku": p1.sku, "sale_price": "149.99"},   # valid change
        {"sku": p2.sku, "sale_price": "200.00"},   # unchanged -> not counted
        {"sku": "NOPE-404", "sale_price": "50"},   # unknown SKU
        {"sku": "", "sale_price": "10"},           # missing SKU
        {"sku": "BAD-1", "sale_price": "-5"},      # invalid price
    ]
    path = tmp_path / "updates.json"
    path.write_text(json.dumps(updates), encoding="utf-8")

    summary = WebsiteSyncService.import_price_updates(context=admin_context, session=session,
                                                      input_path=str(path))
    assert summary["updated_count"] == 1
    assert summary["updated"][0]["sku"] == p1.sku
    assert summary["updated"][0]["old_price"] == 100.00
    assert summary["updated"][0]["new_price"] == 149.99
    assert summary["unknown_skus"] == ["NOPE-404"]
    assert len(summary["errors"]) == 2

    # Price actually persisted
    from src.modules.inventory.models import Product
    fresh = session.query(Product).filter(Product.id == p1.id).first()
    assert fresh.sale_price == Decimal("149.99")


def test_import_accepts_products_wrapper(tmp_path, session, admin_context):
    """Object with a 'products' key is accepted too."""
    product = _product(session, admin_context, price="300.00")
    path = tmp_path / "updates.json"
    path.write_text(json.dumps({"products": [{"sku": product.sku, "sale_price": "399.00"}]}),
                    encoding="utf-8")
    summary = WebsiteSyncService.import_price_updates(context=admin_context, session=session,
                                                      input_path=str(path))
    assert summary["updated_count"] == 1


def test_import_rejects_bad_structure(tmp_path, session, admin_context):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"just": "a dict"}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        WebsiteSyncService.import_price_updates(context=admin_context, session=session,
                                                input_path=str(path))