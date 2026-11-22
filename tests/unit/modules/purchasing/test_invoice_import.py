"""Tests for importing a reviewed scan as a Draft purchase."""

import json
from datetime import date
from decimal import Decimal

import pytest

from src.core.context import RequestContext
from src.modules.inventory.models import Brand, Category, Product, ProductType
from src.modules.purchasing.invoice_import import InvoiceImportService
from src.modules.purchasing.models import (
    Purchase,
    PurchaseState,
    SupplierInvoiceProfile,
)
from src.modules.suppliers.models import Supplier
from src.security.permissions import AccessDenied

COLUMNS = {
    "reference": (0.02, 0.16),
    "label": (0.17, 0.65),
    "quantity": (0.68, 0.74),
    "unit_cost": (0.75, 0.84),
    "amount": (0.86, 0.96),
}


@pytest.fixture
def admin_context():
    return RequestContext(
        user_id="1",
        username="admin",
        role="Administrator",
        permissions={
            "Purchasing.Purchases.View",
            "Purchasing.Purchases.Create",
            "Purchasing.Purchases.Update",
            "Purchasing.Purchases.Validate",
            "Suppliers.Suppliers.View",
            "Inventory.Products.View",
        },
    )


@pytest.fixture
def supplier(session):
    row = Supplier(company_name="TCL Maroc", ice_number="003947029000043")
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def product(session):
    session.add_all([Category(name="Climatisation"), Brand(name="TCL")])
    session.flush()
    row = Product(
        name="Split TCL 9000 BTU",
        sku="RAC-09CHSD/ZG311",
        product_type=ProductType.PHYSICAL,
        purchase_price=Decimal("2274.35"),
        sale_price=Decimal("2999.00"),
    )
    session.add(row)
    session.flush()
    return row


def _save(session, context, supplier, product, **overrides):
    options = dict(
        file_path="C:/scans/tcl_9660007552.pdf",
        file_hash="a" * 64,
        fingerprint="f" * 40,
        supplier_id=supplier.id,
        reference="PUR-2026-0001",
        invoice_no="9660007552",
        invoice_date=date(2026, 9, 22),
        items=[{
            "product_id": product.id,
            "quantity": 2,
            "unit_cost": "2274.35",
            "reference": "RAC-09CHSD/ZG311",
            "label": "Split TCL 9000 BTU",
        }],
        columns=COLUMNS,
        remember_format=True,
    )
    options.update(overrides)
    return InvoiceImportService.save_scan(context, session, **options)


def test_saves_scan_as_draft_with_paper_fields(session, admin_context, supplier, product):
    purchase = _save(session, admin_context, supplier, product)

    assert purchase.state == PurchaseState.DRAFT
    assert purchase.supplier_id == supplier.id
    assert purchase.supplier_invoice_no == "9660007552"
    assert purchase.purchase_date == date(2026, 9, 22)
    assert purchase.source_file_hash == "a" * 64
    assert purchase.source_file_name == "tcl_9660007552.pdf"
    assert purchase.total_amount == Decimal("4548.70")
    assert len(purchase.items) == 1
    assert purchase.items[0].quantity == 2
    assert purchase.items[0].unit_cost == Decimal("2274.35")


def test_validation_is_not_triggered_by_import(session, admin_context, supplier, product):
    purchase = _save(session, admin_context, supplier, product)

    assert purchase.state == PurchaseState.DRAFT
    from src.modules.inventory.models import StockMovement
    assert session.query(StockMovement).count() == 0


def test_refuses_same_invoice_number_from_supplier(session, admin_context, supplier, product):
    _save(session, admin_context, supplier, product)

    with pytest.raises(ValueError, match="already imported"):
        _save(session, admin_context, supplier, product, file_hash="b" * 64, reference="PUR-2026-0002")


def test_refuses_same_scan_file(session, admin_context, supplier, product):
    _save(session, admin_context, supplier, product)

    with pytest.raises(ValueError, match="exact scan was already imported"):
        _save(session, admin_context, supplier, product,
              invoice_no="OTHER-1", reference="PUR-2026-0002")


def test_same_invoice_number_from_another_supplier_is_allowed(session, admin_context, supplier, product):
    other = Supplier(company_name="Ariha", ice_number="001733780000043")
    session.add(other)
    session.flush()
    _save(session, admin_context, supplier, product)

    purchase = _save(session, admin_context, other, product,
                     file_hash="b" * 64, reference="PUR-2026-0002")

    assert purchase.supplier_id == other.id
    assert purchase.supplier_invoice_no == "9660007552"


def test_refuses_line_without_product(session, admin_context, supplier, product):
    with pytest.raises(ValueError, match="has no product"):
        _save(session, admin_context, supplier, product,
              items=[{"product_id": None, "quantity": 2, "unit_cost": "10.00", "label": "Unknown"}])


def test_refuses_archived_supplier(session, admin_context, supplier, product):
    supplier.is_archived = True
    session.flush()

    with pytest.raises(ValueError, match="archived"):
        _save(session, admin_context, supplier, product)


def test_requires_create_permission(session, supplier, product):
    viewer = RequestContext(
        user_id="9", username="viewer", role="Viewer",
        permissions={"Purchasing.Purchases.View"},
    )

    with pytest.raises(AccessDenied):
        _save(session, viewer, supplier, product)


def test_keeps_reference_unique(session, admin_context, supplier, product):
    _save(session, admin_context, supplier, product)
    second = _save(session, admin_context, supplier, product,
                   file_hash="b" * 64, invoice_no="9660007553", reference="PUR-2026-0001")

    assert second.reference == "PUR-2026-0001-2"


def test_remembers_layout_once_per_supplier_and_fingerprint(session, admin_context, supplier, product):
    _save(session, admin_context, supplier, product)
    _save(session, admin_context, supplier, product,
          file_hash="b" * 64, invoice_no="9660007553", reference="PUR-2026-0002")

    profiles = session.query(SupplierInvoiceProfile).all()
    assert len(profiles) == 1
    assert profiles[0].supplier_id == supplier.id
    assert profiles[0].fingerprint == "f" * 40
    assert json.loads(profiles[0].rules_json)["columns"]["amount"] == list(COLUMNS["amount"])


def test_can_skip_remembering_layout(session, admin_context, supplier, product):
    _save(session, admin_context, supplier, product, remember_format=False)

    assert session.query(SupplierInvoiceProfile).count() == 0
    assert session.query(Purchase).count() == 1
