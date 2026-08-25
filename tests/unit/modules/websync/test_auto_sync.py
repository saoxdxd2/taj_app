import json
import uuid

import pytest
from decimal import Decimal

from src.modules.websync.services import WebsiteSyncService
from src.modules.websync import sync_config
from src.modules.inventory.services import InventoryService
from src.core.context import RequestContext


@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})


@pytest.fixture
def sync_folder(tmp_path, monkeypatch):
    """Point the sync config at a temp folder for this test."""
    folder = tmp_path / "sync"
    folder.mkdir(parents=True)
    monkeypatch.setattr(sync_config, "DEFAULT_SYNC_FOLDER", folder)
    monkeypatch.setattr(sync_config, "_CONFIG_FILE", tmp_path / "cfg.json")
    return folder


def _product(session, admin_context, price="250.00"):
    sku = f"AUTO-{uuid.uuid4().hex[:8]}"
    product = InventoryService.create_product(
        context=admin_context, session=session,
        name=f"Auto {sku}", sku=sku,
        purchase_price=Decimal("150"), sale_price=Decimal(price),
    )
    InventoryService.activate_product(context=admin_context, session=session, product_id=product.id)
    InventoryService.adjust_stock(
        context=admin_context, session=session, product_id=product.id,
        quantity_change=9, movement_type="Purchase", reference=f"INIT-{sku}",
    )
    return product


def test_auto_export_writes_catalog_to_sync_folder(sync_folder):
    """auto_export_catalog writes website_catalog.json into the sync folder."""
    result = WebsiteSyncService.auto_export_catalog()
    assert result is not None
    assert result["path"].endswith("website_catalog.json")

    data = json.loads((sync_folder / "website_catalog.json").read_text(encoding="utf-8"))
    assert "products" in data
    # no leftover temp file
    assert not (sync_folder / "website_catalog.tmp").exists()


def test_process_pending_updates_applies_and_archives(sync_folder, session, db_engine,
                                                      admin_context, monkeypatch):
    """A dropped price_updates.json is applied and archived (not re-applied)."""
    # Bind the auto path to the same in-memory DB as the test session
    from sqlalchemy.orm import sessionmaker
    import src.database.session as db_session_module
    monkeypatch.setattr(db_session_module, "SessionLocal", sessionmaker(bind=db_engine))

    product = _product(session, admin_context, price="250.00")
    session.commit()

    updates = [{"sku": product.sku, "sale_price": "199.00"}]
    (sync_folder / "price_updates.json").write_text(json.dumps(updates), encoding="utf-8")

    summary = WebsiteSyncService.process_pending_updates()
    assert summary is not None
    assert summary["updated_count"] == 1

    # Price persisted in DB (visible through a fresh session on the same engine)
    from src.modules.inventory.models import Product
    check_session = sessionmaker(bind=db_engine)()
    fresh = check_session.query(Product).filter(Product.id == product.id).first()
    assert fresh.sale_price == Decimal("199.00")
    check_session.close()

    # Pending file archived with applied- prefix; nothing pending anymore
    pending = list(sync_folder.glob("price_updates.applied-*.json"))
    assert len(pending) == 1
    assert not (sync_folder / "price_updates.json").exists()

    # Second run: nothing to do
    assert WebsiteSyncService.process_pending_updates() is None


def test_process_pending_updates_noop_when_empty(sync_folder):
    assert WebsiteSyncService.process_pending_updates() is None


def test_sync_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_config, "_CONFIG_FILE", tmp_path / "cfg.json")
    target = tmp_path / "custom_sync"
    folder = sync_config.set_sync_folder(target)
    assert folder.exists()
    assert sync_config.get_sync_folder() == target