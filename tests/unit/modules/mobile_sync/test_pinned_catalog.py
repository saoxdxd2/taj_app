"""Catalog push fields/filter and pulled-pin application rules."""
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from src.modules.audit.models import AuditEvent
from src.modules.inventory.models import Product, ProductState
from src.modules.mobile_sync import catalog, sync


EXPECTED_KEYS = {
    "sku", "name", "sale_price", "pinned_price", "effective_price", "priced",
    "vat_rate", "stock", "active", "category", "brand",
}
EXPECTED_PRICE_KEYS = {"sale_price", "pinned_price", "effective_price", "priced"}


@pytest.fixture
def catalog_db(db_engine, monkeypatch):
    """Run build_catalog_payload against the migrated in-memory engine."""
    TestSession = sessionmaker(bind=db_engine)
    monkeypatch.setattr("src.database.session.SessionLocal", TestSession)
    with TestSession() as session:
        yield session


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "mobile_sync_state.json"
    monkeypatch.setattr(sync, "STATE_FILE", path)
    return path


class CatalogClient:
    def __init__(self, payload):
        self.payload = payload

    def get_catalog(self, since_version):
        return self.payload


def _product(session, sku, *, sale_price="0.00", pin=None,
             state=ProductState.DRAFT):
    product = Product(
        name=f"Name {sku}", sku=sku, sale_price=Decimal(sale_price),
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
        .all()
    )


def test_catalog_payload_fields_and_unpriced_filter(catalog_db, admin_context):
    _product(catalog_db, "UNPRICED")                         # 0 base, no pin
    _product(catalog_db, "BASE", sale_price="100.00")
    _product(catalog_db, "PINNED", pin=Decimal("149.00"))

    payload = catalog.build_catalog_payload(admin_context, base_revision=7)

    assert payload["baseRevision"] == 7
    assert isinstance(payload["version"], int)
    by_sku = {p["sku"]: p for p in payload["products"]}
    assert set(by_sku) == {"BASE", "PINNED"}

    for product in by_sku.values():
        assert set(product) == EXPECTED_KEYS
        assert {k for k in product if k in EXPECTED_PRICE_KEYS} == EXPECTED_PRICE_KEYS
        assert product["priced"] is True
        assert product["pinned_price"] is not None

    base = by_sku["BASE"]
    assert base["sale_price"] == "100.00"
    assert base["pinned_price"] == ""
    assert base["effective_price"] == "100.00"

    pinned = by_sku["PINNED"]
    assert pinned["sale_price"] == "0.00"
    assert pinned["pinned_price"] == "149.00"
    assert pinned["effective_price"] == "149.00"
    assert pinned["active"] is False


def test_catalog_version_changes_when_pin_changes(catalog_db, admin_context):
    product = _product(catalog_db, "VERSION", sale_price="100.00")
    before = catalog.build_catalog_payload(admin_context)["version"]

    product.pinned_price = Decimal("101.00")
    catalog_db.flush()
    after = catalog.build_catalog_payload(admin_context)["version"]

    assert after != before


def test_pull_applies_snapshot_pins_by_sku(state_file, session, admin_context):
    to_pin = _product(session, "REMOTE-SET")
    to_clear = _product(session, "REMOTE-CLEAR", pin=Decimal("50.00"),
                        state=ProductState.ACTIVE)
    keep_null = _product(session, "REMOTE-NULL", pin=Decimal("77.00"),
                         state=ProductState.ACTIVE)
    missing = _product(session, "REMOTE-MISSING", pin=Decimal("88.00"),
                       state=ProductState.ACTIVE)

    payload = {
        "version": 123,
        "products": [
            {"sku": "REMOTE-SET", "pinned_price": "149.00"},
            {"sku": "REMOTE-CLEAR", "pinned_price": ""},
            {"sku": "REMOTE-NULL", "pinned_price": None},
            # REMOTE-MISSING is deliberately absent: its pin must survive.
        ],
    }
    state = sync.load_state()
    state["last_pushed_pins"] = {
        "REMOTE-SET": "", "REMOTE-CLEAR": "50.00", "REMOTE-NULL": "77.00",
    }
    sync.save_state(state)

    version, products = sync.pull_catalog(
        CatalogClient(payload), 0, context=admin_context, session=session
    )

    assert version == 123
    assert len(products) == 3
    session.refresh(to_pin)
    session.refresh(to_clear)
    session.refresh(keep_null)
    session.refresh(missing)
    assert to_pin.pinned_price == Decimal("149.00")
    assert to_pin.state == ProductState.ACTIVE
    assert to_clear.pinned_price is None
    assert to_clear.state == ProductState.ACTIVE
    assert keep_null.pinned_price == Decimal("77.00")
    assert missing.pinned_price == Decimal("88.00")
    assert len(_update_events(session, to_pin)) == 1
    assert len(_update_events(session, to_clear)) == 1
    assert sync.load_state()["last_pulled_version"] == 123


def test_pull_deduplicates_skus_to_avoid_repeat_audit_events(
    state_file, session, admin_context,
):
    product = _product(session, "REMOTE-DUP")
    payload = {
        "version": 5,
        "products": [
            {"sku": "REMOTE-DUP", "pinned_price": "10.00"},
            {"sku": "REMOTE-DUP", "pinned_price": "20.00"},
        ],
    }
    state = sync.load_state()
    state["last_pushed_pins"] = {"REMOTE-DUP": ""}
    sync.save_state(state)

    sync.pull_catalog(CatalogClient(payload), 0,
                      context=admin_context, session=session)

    session.refresh(product)
    assert product.pinned_price == Decimal("20.00")
    assert len(_update_events(session, product)) == 1


def test_pull_preserves_local_pin_when_relay_pin_is_unchanged(
    state_file, session,
):
    """A pin set locally after the last push must survive an old relay snapshot."""
    product = _product(session, "LOCAL-ONLY", pin=Decimal("55.00"),
                       state=ProductState.ACTIVE)
    state = sync.load_state()
    state["last_pushed_pins"] = {"LOCAL-ONLY": ""}
    sync.save_state(state)

    payload = {
        "version": 9,
        "products": [{"sku": "LOCAL-ONLY", "pinned_price": ""}],
    }
    # No context is passed: trusted sync apply must not require the UI user to
    # hold Inventory.Products.Update.
    sync.pull_catalog(CatalogClient(payload), 0, session=session)

    session.refresh(product)
    assert product.pinned_price == Decimal("55.00")
    assert len(_update_events(session, product)) == 0
