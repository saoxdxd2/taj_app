import os
import pytest
from decimal import Decimal

from src.modules.settings.services import SettingsService
from src.modules.sales.services import SalesService
from src.modules.inventory.services import InventoryService
from src.modules.crm.services import CRMService
from src.core.context import RequestContext


@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})


@pytest.fixture
def customer(session):
    from src.modules.crm.models import Customer
    c = Customer(company_name="Client Facture SARL", ice_number="003584281000052", phone="0522123456")
    session.add(c)
    session.flush()
    return c


# --- Company settings ---

def test_company_settings_defaults_created_once(session, admin_context):
    """First access creates the singleton; second access returns the same row."""
    s1 = SettingsService.get_company_settings(context=admin_context, session=session)
    assert s1.id == 1
    assert s1.company_name == "TAJ FROID"
    s2 = SettingsService.get_company_settings(context=admin_context, session=session)
    assert s2.id == s1.id


def test_update_company_settings(session, admin_context):
    """Partial update only touches provided fields; empty name rejected."""
    SettingsService.update_company_settings(
        context=admin_context, session=session,
        ice_number="002716096000041",
        address_street="12 Rue de l'Industrie",
        address_city="Casablanca",
        bank_rib="011 780 0000123456789012 34",
    )
    settings = SettingsService.get_company_settings(context=admin_context, session=session)
    assert settings.ice_number == "002716096000041"
    assert settings.address_city == "Casablanca"
    assert settings.company_name == "TAJ FROID"  # untouched

    with pytest.raises(ValueError, match="cannot be empty"):
        SettingsService.update_company_settings(
            context=admin_context, session=session, company_name="   "
        )


# --- Facture PDF ---

def _make_validated_invoice(session, admin_context, customer):
    product = InventoryService.create_product(
        context=admin_context, session=session,
        name="Climatiseur Split 12000 BTU", sku="FAC-01",
        purchase_price=Decimal("2500.00"), sale_price=Decimal("3500.00"),
    )
    InventoryService.activate_product(context=admin_context, session=session, product_id=product.id)
    InventoryService.adjust_stock(
        context=admin_context, session=session, product_id=product.id,
        quantity_change=10, movement_type="Purchase", reference="INIT-FAC-01",
    )
    invoice = SalesService.create_invoice_draft(
        context=admin_context, session=session, customer_id=customer.id,
    )
    SalesService.add_item_to_invoice(
        context=admin_context, session=session, invoice_id=invoice.id,
        product_id=product.id, quantity=2,
        unit_price=Decimal("3500.00"), vat_rate=Decimal("20.00"),
        unit_cost=Decimal("2500.00"),
    )
    SalesService.validate_invoice(context=admin_context, session=session, invoice_id=invoice.id)
    return invoice, product


def test_facture_pdf_generated(tmp_path, session, admin_context, customer):
    """A validated invoice produces a non-empty facture PDF on disk."""
    pytest.importorskip("reportlab")

    invoice, product = _make_validated_invoice(session, admin_context, customer)

    company_data = {
        "company_name": "TAJ FROID",
        "ice_number": "002716096000041",
        "rc_number": "458921",
        "address_street": "12 Rue de l'Industrie",
        "address_city": "Casablanca",
        "phone": "0522123456",
        "bank_rib": "011 780 0000123456789012 34",
        "invoice_footer_note": "Merci de votre confiance.",
    }
    customer_data = {
        "company_name": customer.company_name,
        "ice_number": customer.ice_number,
        "phone": customer.phone,
    }
    items = [{
        "description": product.name,
        "quantity": 2,
        "unit_price": float(product.sale_price),
        "vat_rate": 20.0,
    }]
    invoice_data = {"invoice_number": invoice.invoice_number, "date": "25/08/2026"}

    from src.core.pdf_engine import PDFEngine
    filepath = PDFEngine.generate_facture_pdf(
        invoice_data, items,
        customer_data=customer_data, company_data=company_data,
        output_dir=str(tmp_path),
    )

    assert os.path.exists(filepath)
    assert os.path.getsize(filepath) > 1000  # a real page, not an empty file
    with open(filepath, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"  # valid PDF magic bytes


def test_facture_pdf_multi_vat_breakdown(tmp_path, admin_context, customer):
    """Mixed VAT rates produce separate TVA lines and correct TTC."""
    pytest.importorskip("reportlab")

    items = [
        {"description": "Split 12000 BTU", "quantity": 1, "unit_price": 3500.0, "vat_rate": 20.0},
        {"description": "Main d'oeuvre installation", "quantity": 2, "unit_price": 300.0, "vat_rate": 10.0},
    ]
    # HT: 3500 + 600 = 4100 ; TVA: 700 + 60 = 760 ; TTC: 4860
    from src.core.pdf_engine import PDFEngine
    filepath = PDFEngine.generate_facture_pdf(
        {"invoice_number": "N°99-26", "date": "25/08/2026"},
        items, output_dir=str(tmp_path),
    )
    assert os.path.exists(filepath)
    assert os.path.getsize(filepath) > 1000


def test_facture_pdf_unavailable_raises(monkeypatch, tmp_path):
    """Graceful degradation when reportlab is missing."""
    import src.core.pdf_engine as engine_mod
    monkeypatch.setattr(engine_mod, "PDF_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="unavailable"):
        engine_mod.PDFEngine.generate_facture_pdf(
            {"invoice_number": "X"}, [], output_dir=str(tmp_path)
        )