import uuid

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.modules.finance.services import FinanceService
from src.modules.sales.services import SalesService
from src.modules.inventory.services import InventoryService
from src.modules.crm.models import Customer
from src.core.context import RequestContext


@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})


@pytest.fixture
def customer(session):
    c = Customer(company_name="Debtor SARL", ice_number="003584281000052")
    session.add(c)
    session.flush()
    return c


def _validated_invoice(session, admin_context, customer, sku=None, qty=2,
                       cost="100.00", price="150.00"):
    if sku is None:
        sku = f"ANL-{uuid.uuid4().hex[:8]}"  # unique per call (SKU is unique)
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
    invoice = SalesService.create_invoice_draft(
        context=admin_context, session=session, customer_id=customer.id,
    )
    SalesService.add_item_to_invoice(
        context=admin_context, session=session, invoice_id=invoice.id,
        product_id=product.id, quantity=qty,
        unit_price=Decimal(price), vat_rate=Decimal("20.00"),
        unit_cost=Decimal(cost),
    )
    SalesService.validate_invoice(context=admin_context, session=session, invoice_id=invoice.id)
    return invoice


# --- Cash flow ---

def test_cash_flow_current_month(session, admin_context, customer):
    """Inflow from payments, outflow from expenses; net computed correctly."""
    invoice = _validated_invoice(session, admin_context, customer)
    SalesService.register_payment(context=admin_context, session=session,
                                  invoice_id=invoice.id, method="Cash",
                                  amount=Decimal("360.00"))
    FinanceService.record_expense(session=session, reference="DEP-001",
                                  description="Electricity", amount=Decimal("500.00"))

    flow = FinanceService.get_cash_flow(context=admin_context, session=session)
    assert flow["inflow"] >= Decimal("360.00")
    assert flow["outflow"] >= Decimal("500.00")
    # net must reflect at least these two entries
    assert flow["net"] == flow["inflow"] - flow["outflow"]
    assert "Payment Received" in flow["breakdown"]
    assert flow["breakdown"]["Expense"] == Decimal("-500.00")


def test_cash_flow_validates_range(session, admin_context):
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="before end"):
        FinanceService.get_cash_flow(context=admin_context, session=session,
                                     start=now, end=now)


# --- Debtors ---

def test_debtors_lists_only_owing_customers(session, admin_context):
    owing = Customer(company_name="Owing SARL")
    settled = Customer(company_name="Settled SARL")
    session.add_all([owing, settled])
    session.flush()

    inv1 = _validated_invoice(session, admin_context, owing)          # 360 total
    inv2 = _validated_invoice(session, admin_context, settled)

    debtors = FinanceService.get_debtors(context=admin_context, session=session)
    by_name = {d["company_name"]: d for d in debtors}

    assert "Owing SARL" in by_name
    assert by_name["Owing SARL"]["outstanding"] == Decimal("360.00")
    assert by_name["Owing SARL"]["total_invoiced"] == Decimal("360.00")
    assert by_name["Owing SARL"]["total_paid"] == Decimal("0.00")
    # Both owe money at this point (nothing paid yet)
    assert "Settled SARL" in by_name

    # Pay the second invoice fully -> disappears from debtors
    SalesService.register_payment(context=admin_context, session=session,
                                  invoice_id=inv2.id, method="Cash",
                                  amount=Decimal("360.00"))
    debtors_after = FinanceService.get_debtors(context=admin_context, session=session)
    assert "Settled SARL" not in {d["company_name"] for d in debtors_after}


# --- Monthly profit series ---

def test_monthly_profit_series_buckets_by_month(session, admin_context, customer):
    _validated_invoice(session, admin_context, customer, sku="SER-01")  # HT 300, cost 200

    year = datetime.now(timezone.utc).year
    series = FinanceService.get_monthly_profit_series(context=admin_context,
                                                      session=session, year=year)
    assert len(series) == 12
    current = series[datetime.now(timezone.utc).month - 1]
    assert current["revenue_excl_vat"] == Decimal("300.00")
    assert current["total_cost"] == Decimal("200.00")
    assert current["gross_margin"] == Decimal("100.00")
    # all other months empty
    others = [m for m in series if m["month"] != datetime.now(timezone.utc).month]
    assert all(m["revenue_excl_vat"] == Decimal("0.00") for m in others)


def test_monthly_profit_series_validates_year(session, admin_context):
    with pytest.raises(ValueError, match="Invalid year"):
        FinanceService.get_monthly_profit_series(context=admin_context,
                                                 session=session, year=1800)