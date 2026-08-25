import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.modules.sales.services import SalesService
from src.modules.crm.services import CRMService
from src.modules.purchasing.services import PurchasingService
from src.modules.reports.services import ReportsService
from src.modules.inventory.services import InventoryService
from src.modules.crm.models import Customer
from src.modules.suppliers.models import Supplier
from src.core.context import RequestContext


@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})


@pytest.fixture
def customer(session):
    c = Customer(company_name="Client Stats SARL", ice_number="003584281000052")
    session.add(c)
    session.flush()
    return c


@pytest.fixture
def supplier(session):
    s = Supplier(company_name="Fournisseur Froid SARL")
    session.add(s)
    session.flush()
    return s


def _stocked_product(session, admin_context, sku, cost="100.00", price="150.00"):
    product = InventoryService.create_product(
        context=admin_context, session=session,
        name=f"Product {sku}", sku=sku,
        purchase_price=Decimal(cost), sale_price=Decimal(price),
    )
    InventoryService.activate_product(context=admin_context, session=session, product_id=product.id)
    InventoryService.adjust_stock(
        context=admin_context, session=session, product_id=product.id,
        quantity_change=50, movement_type="Purchase", reference=f"INIT-{sku}",
    )
    return product


# --- Invoice auto-numbering ---

def test_invoice_numbering_sequence(session, admin_context, customer):
    """Numbers follow N°01-YY, N°02-YY ... per year."""
    yy = f"{datetime.now(timezone.utc).year % 100:02d}"
    inv1 = SalesService.create_invoice_draft(context=admin_context, session=session, customer_id=customer.id)
    inv2 = SalesService.create_invoice_draft(context=admin_context, session=session, customer_id=customer.id)
    assert inv1.invoice_number == f"N°01-{yy}"
    assert inv2.invoice_number == f"N°02-{yy}"


def test_invoice_numbering_continues_after_manual_numbers(session, admin_context, customer):
    """Manual/legacy numbers are respected: next auto number skips past them."""
    yy = f"{datetime.now(timezone.utc).year % 100:02d}"
    SalesService.create_invoice_draft(context=admin_context, session=session,
                                      customer_id=customer.id, invoice_number=f"N°07-{yy}")
    inv = SalesService.create_invoice_draft(context=admin_context, session=session, customer_id=customer.id)
    assert inv.invoice_number == f"N°08-{yy}"


def test_invoice_numbering_ignores_other_formats(session, admin_context, customer):
    """Old-format numbers (FACT-...) do not interfere with the sequence."""
    SalesService.create_invoice_draft(context=admin_context, session=session,
                                      customer_id=customer.id, invoice_number="FACT-LEGACY-001")
    inv = SalesService.create_invoice_draft(context=admin_context, session=session, customer_id=customer.id)
    yy = f"{datetime.now(timezone.utc).year % 100:02d}"
    assert inv.invoice_number == f"N°01-{yy}"


# --- CRM trade stats ---

def test_customer_trade_stats(session, admin_context, customer):
    """Invoiced / paid / outstanding / deposits per client."""
    product = _stocked_product(session, admin_context, "STAT-01")
    inv = SalesService.create_invoice_draft(context=admin_context, session=session, customer_id=customer.id)
    SalesService.add_item_to_invoice(
        context=admin_context, session=session, invoice_id=inv.id,
        product_id=product.id, quantity=2,
        unit_price=Decimal("150.00"), vat_rate=Decimal("20.00"),
        unit_cost=Decimal("100.00"),
    )
    SalesService.validate_invoice(context=admin_context, session=session, invoice_id=inv.id)
    # total = 360; pay 200 now
    SalesService.register_payment(context=admin_context, session=session,
                                  invoice_id=inv.id, method="Cash", amount=Decimal("200.00"))
    # an open bon of 500
    SalesService.create_deposit(context=admin_context, session=session,
                                deposit_number="BON-ST-01", customer_id=customer.id,
                                amount=Decimal("500.00"), method="Cash")

    stats = CRMService.get_customer_trade_stats(context=admin_context, session=session, customer_id=customer.id)
    assert stats["invoices_count"] == 1
    assert stats["total_invoiced"] == Decimal("360.00")
    assert stats["total_paid"] == Decimal("200.00")
    assert stats["outstanding_balance"] == Decimal("160.00")
    assert stats["available_deposits"] == Decimal("500.00")
    assert stats["last_purchase"] is not None


def test_trade_stats_unknown_customer_raises(session, admin_context):
    with pytest.raises(ValueError, match="not found"):
        CRMService.get_customer_trade_stats(context=admin_context, session=session, customer_id=9999)


# --- Purchase -> cost history ---

def test_cost_history_and_last_cost(session, admin_context, customer, supplier):
    """Validated purchases build the real cost history; drafts are excluded."""
    product = _stocked_product(session, admin_context, "COST-01")

    p1 = PurchasingService.create_purchase_draft(context=admin_context, session=session,
                                                 reference="ACH-001", supplier_id=supplier.id)
    PurchasingService.add_item_to_purchase(context=admin_context, session=session,
                                           purchase_id=p1.id, product_id=product.id,
                                           quantity=10, unit_cost=Decimal("95.00"))
    PurchasingService.validate_purchase(context=admin_context, session=session, purchase_id=p1.id)

    # A DRAFT purchase must NOT appear in history
    p_draft = PurchasingService.create_purchase_draft(context=admin_context, session=session,
                                                      reference="ACH-DRAFT", supplier_id=supplier.id)
    PurchasingService.add_item_to_purchase(context=admin_context, session=session,
                                           purchase_id=p_draft.id, product_id=product.id,
                                           quantity=5, unit_cost=Decimal("1.00"))

    p2 = PurchasingService.create_purchase_draft(context=admin_context, session=session,
                                                 reference="ACH-002", supplier_id=supplier.id)
    PurchasingService.add_item_to_purchase(context=admin_context, session=session,
                                           purchase_id=p2.id, product_id=product.id,
                                           quantity=8, unit_cost=Decimal("99.50"))
    PurchasingService.validate_purchase(context=admin_context, session=session, purchase_id=p2.id)

    history = PurchasingService.get_product_cost_history(context=admin_context, session=session,
                                                         product_id=product.id)
    assert len(history) == 2  # draft excluded
    assert history[0]["unit_cost"] == Decimal("99.50")   # newest first
    assert history[0]["reference"] == "ACH-002"
    assert history[0]["supplier"] == "Fournisseur Froid SARL"  # company_name
    assert history[1]["unit_cost"] == Decimal("95.00")

    last = PurchasingService.get_last_purchase_cost(context=admin_context, session=session,
                                                    product_id=product.id)
    assert last == Decimal("99.50")


def test_last_cost_none_when_never_purchased(session, admin_context):
    product = _stocked_product(session, admin_context, "NEVER-01")
    last = PurchasingService.get_last_purchase_cost(context=admin_context, session=session,
                                                    product_id=product.id)
    assert last is None


# --- Profit engine ---

def test_invoice_profit_exact(session, admin_context, customer):
    """Margin uses captured unit_cost and VAT-exclusive revenue."""
    product = _stocked_product(session, admin_context, "PROFIT-01", cost="100.00", price="150.00")
    inv = SalesService.create_invoice_draft(context=admin_context, session=session, customer_id=customer.id)
    SalesService.add_item_to_invoice(
        context=admin_context, session=session, invoice_id=inv.id,
        product_id=product.id, quantity=3,
        unit_price=Decimal("150.00"), vat_rate=Decimal("20.00"),
        unit_cost=Decimal("100.00"),
    )
    SalesService.validate_invoice(context=admin_context, session=session, invoice_id=inv.id)

    profit = ReportsService.calculate_invoice_profit(context=admin_context, session=session, invoice_id=inv.id)
    assert profit["revenue_excl_vat"] == Decimal("450.00")   # 3 x 150 (no VAT)
    assert profit["total_cost"] == Decimal("300.00")         # 3 x 100
    assert profit["gross_margin"] == Decimal("150.00")
    assert profit["margin_percent"] == Decimal("33.33")


def test_invoice_profit_rejected_on_draft(session, admin_context, customer):
    inv = SalesService.create_invoice_draft(context=admin_context, session=session, customer_id=customer.id)
    with pytest.raises(ValueError, match="validated"):
        ReportsService.calculate_invoice_profit(context=admin_context, session=session, invoice_id=inv.id)


def test_period_profit_aggregates(session, admin_context, customer):
    """Period totals across invoices, computed server-side."""
    p1 = _stocked_product(session, admin_context, "PER-01", cost="100.00", price="150.00")
    p2 = _stocked_product(session, admin_context, "PER-02", cost="200.00", price="300.00")

    for sku_prod, qty in ((p1, 2), (p2, 1)):
        inv = SalesService.create_invoice_draft(context=admin_context, session=session, customer_id=customer.id)
        SalesService.add_item_to_invoice(
            context=admin_context, session=session, invoice_id=inv.id,
            product_id=sku_prod.id, quantity=qty,
            unit_price=sku_prod.sale_price, vat_rate=Decimal("20.00"),
            unit_cost=sku_prod.purchase_price,
        )
        SalesService.validate_invoice(context=admin_context, session=session, invoice_id=inv.id)

    now = datetime.now(timezone.utc)
    report = ReportsService.calculate_period_profit(
        context=admin_context, session=session,
        start=now - timedelta(days=1), end=now + timedelta(days=1),
    )
    assert report["invoices_count"] == 2
    assert report["revenue_excl_vat"] == Decimal("600.00")   # 300 + 300
    assert report["total_cost"] == Decimal("400.00")         # 200 + 200
    assert report["gross_margin"] == Decimal("200.00")


def test_period_profit_validates_range(session, admin_context):
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="before end"):
        ReportsService.calculate_period_profit(context=admin_context, session=session,
                                               start=now, end=now)


def test_top_products_by_margin(session, admin_context, customer):
    """Ranking puts the higher-margin product first."""
    cheap = _stocked_product(session, admin_context, "TOP-01", cost="100.00", price="200.00")  # 50%
    pricey = _stocked_product(session, admin_context, "TOP-02", cost="250.00", price="300.00")  # ~17%

    for prod in (cheap, pricey):
        inv = SalesService.create_invoice_draft(context=admin_context, session=session, customer_id=customer.id)
        SalesService.add_item_to_invoice(
            context=admin_context, session=session, invoice_id=inv.id,
            product_id=prod.id, quantity=1,
            unit_price=prod.sale_price, vat_rate=Decimal("20.00"),
            unit_cost=prod.purchase_price,
        )
        SalesService.validate_invoice(context=admin_context, session=session, invoice_id=inv.id)

    now = datetime.now(timezone.utc)
    top = ReportsService.get_top_products_by_margin(
        context=admin_context, session=session,
        start=now - timedelta(days=1), end=now + timedelta(days=1),
    )
    assert len(top) == 2
    assert top[0]["sku"] == "TOP-01"
    assert top[0]["gross_margin"] == Decimal("100.00")
    assert top[1]["sku"] == "TOP-02"