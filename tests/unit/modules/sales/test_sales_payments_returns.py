import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.modules.sales.services import SalesService
from src.modules.sales.models import (
    Invoice, InvoiceItem, InvoiceState, Payment, PaymentMethod,
    CustomerDeposit, DepositState, SalesReturn, ReturnState,
)
from src.modules.inventory.services import InventoryService
from src.modules.finance.services import FinanceService
from src.modules.finance.models import FinancialJournalEntry, TransactionType
from src.modules.crm.models import Customer
from src.core.context import RequestContext
from src.security.permissions import AccessDenied


@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})


@pytest.fixture
def unauthorized_context():
    return RequestContext(user_id="2", username="guest", role="Guest", permissions=set())


def _make_customer(session, name="Test Client SARL"):
    customer = Customer(company_name=name, ice_number="003584281000052")
    session.add(customer)
    session.flush()
    return customer


def _make_stocked_product(session, admin_context, sku, cost="100.00", price="150.00", qty=10):
    product = InventoryService.create_product(
        context=admin_context, session=session,
        name=f"Product {sku}", sku=sku,
        purchase_price=Decimal(cost), sale_price=Decimal(price),
    )
    InventoryService.activate_product(context=admin_context, session=session, product_id=product.id)
    InventoryService.adjust_stock(
        context=admin_context, session=session, product_id=product.id,
        quantity_change=qty, movement_type="Purchase", reference=f"INIT-{sku}",
    )
    return product


def _make_validated_invoice(session, admin_context, customer, sku="CLI-01",
                            cost="100.00", price="150.00", qty=2, warranty_months=12,
                            stock=10):
    product = _make_stocked_product(session, admin_context, sku, cost, price, qty=stock)
    invoice = SalesService.create_invoice_draft(
        context=admin_context, session=session,
        invoice_number=f"FACT-TEST-{sku}", customer_id=customer.id,
    )
    SalesService.add_item_to_invoice(
        context=admin_context, session=session, invoice_id=invoice.id,
        product_id=product.id, quantity=qty,
        unit_price=Decimal(price), vat_rate=Decimal("20.00"),
        unit_cost=Decimal(cost), warranty_months=warranty_months,
    )
    assert SalesService.validate_invoice(context=admin_context, session=session, invoice_id=invoice.id)
    return invoice, product


# --- Cost capture & warranty ---

def test_invoice_captures_unit_cost_and_warranty(session, admin_context):
    """Validated invoice items keep the actual cost and get a warranty end date."""
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer,
                                         cost="100.00", price="150.00", warranty_months=24)
    item = invoice.items[0]
    assert item.unit_cost == Decimal("100.00")
    assert item.warranty_months == 24
    assert item.warranty_end_date is not None
    # 24 months ~ 720 days
    delta = item.warranty_end_date - datetime.now(timezone.utc)
    assert timedelta(days=715) < delta < timedelta(days=725)


# --- Payments ---

def test_payment_cash_updates_balance_and_marks_paid(session, admin_context):
    """Cash payment hits the journal and fully-paid invoices become PAID."""
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    # total = 2 * 150 * 1.2 = 360
    assert invoice.total_amount == Decimal("360.00")

    balance = SalesService.get_invoice_balance(context=admin_context, invoice_id=invoice.id, session=session)
    assert balance == Decimal("360.00")

    SalesService.register_payment(
        context=admin_context, session=session, invoice_id=invoice.id,
        method="Cash", amount=Decimal("360.00"),
    )
    assert invoice.state == InvoiceState.PAID
    assert SalesService.get_invoice_balance(context=admin_context, invoice_id=invoice.id, session=session) == Decimal("0.00")

    entries = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == f"INV-{invoice.invoice_number}",
        FinancialJournalEntry.transaction_type == TransactionType.PAYMENT_RECEIVED,
    ).all()
    assert len(entries) == 1
    assert entries[0].amount == Decimal("360.00")


def test_payment_overpay_rejected(session, admin_context):
    """Paying more than the balance is forbidden."""
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    with pytest.raises(ValueError, match="exceeds remaining balance"):
        SalesService.register_payment(
            context=admin_context, session=session, invoice_id=invoice.id,
            method="Cash", amount=Decimal("1000.00"),
        )


def test_payment_check_defers_journal(session, admin_context):
    """Check payments create a Payment but NO journal entry until the check clears."""
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    SalesService.register_payment(
        context=admin_context, session=session, invoice_id=invoice.id,
        method="Check", amount=Decimal("360.00"), reference="1800089",
    )
    assert invoice.state == InvoiceState.PAID
    entries = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.transaction_type == TransactionType.PAYMENT_RECEIVED,
        FinancialJournalEntry.reference_id == f"INV-{invoice.invoice_number}",
    ).all()
    assert len(entries) == 0  # deferred until check clears


def test_payment_requires_authorized_user(session, unauthorized_context):
    """Unauthorized users cannot register payments."""
    customer = _make_customer(session)
    with pytest.raises(AccessDenied):
        SalesService.register_payment(
            context=unauthorized_context, session=session,
            invoice_id=1, method="Cash", amount=Decimal("10.00"),
        )


# --- Deposits ('bons') ---

def test_deposit_lifecycle(session, admin_context):
    """Create a bon, apply it to an invoice, verify settlement and no double journal."""
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)

    deposit = SalesService.create_deposit(
        context=admin_context, session=session,
        deposit_number="BON-2026-001", customer_id=customer.id,
        amount=Decimal("300.00"), method="Cash",
    )
    assert deposit.state == DepositState.OPEN

    # Deposit money was journaled at creation
    dep_entries = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == "BON-2026-001",
    ).all()
    assert len(dep_entries) == 1

    payment = SalesService.apply_deposit_to_invoice(
        context=admin_context, session=session,
        deposit_id=deposit.id, invoice_id=invoice.id, amount=Decimal("200.00"),
    )
    assert payment.amount == Decimal("200.00")
    assert deposit.state == DepositState.OPEN  # 100 DH still available
    assert deposit.amount_used == Decimal("200.00")
    # Invoice still has a remaining balance (360 - 200)
    assert invoice.state != InvoiceState.PAID
    assert SalesService.get_invoice_balance(context=admin_context, invoice_id=invoice.id, session=session) == Decimal("160.00")

    # Applying more than remaining deposit (100) is rejected
    with pytest.raises(ValueError, match="remaining deposit"):
        SalesService.apply_deposit_to_invoice(
            context=admin_context, session=session,
            deposit_id=deposit.id, invoice_id=invoice.id, amount=Decimal("150.00"),
        )


# --- Returns ---

def test_return_refund_restocks_and_journals(session, admin_context):
    """Validated refund: goods back into stock, money out in the journal."""
    customer = _make_customer(session)
    invoice, product = _make_validated_invoice(session, admin_context, customer, qty=2)

    sales_return = SalesService.create_return(
        context=admin_context, session=session,
        return_number="2026-001", customer_id=customer.id,
        return_type="Refund", invoice_id=invoice.id,
        items=[{"product_id": product.id, "quantity": 1,
                "unit_price": Decimal("150.00"), "reason": "Defective"}],
    )
    assert sales_return.state == ReturnState.DRAFT
    assert sales_return.total_amount == Decimal("150.00")

    SalesService.validate_return(context=admin_context, session=session, return_id=sales_return.id)
    assert sales_return.state == ReturnState.VALIDATED

    # Stock went 10 - 2 (sale) + 1 (return) = 9
    from src.modules.inventory.models import StockLevel
    level = session.query(StockLevel).filter(StockLevel.product_id == product.id).first()
    assert level.quantity == 9

    refund_entries = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == "RET-2026-001",
    ).all()
    assert len(refund_entries) == 1
    assert refund_entries[0].amount == Decimal("-150.00")


def test_return_sent_to_factory_does_not_restock(session, admin_context):
    """Defective units sent to the factory are NOT restocked."""
    customer = _make_customer(session)
    invoice, product = _make_validated_invoice(session, admin_context, customer, qty=2)

    sales_return = SalesService.create_return(
        context=admin_context, session=session,
        return_number="2026-002", customer_id=customer.id,
        return_type="Exchange", invoice_id=invoice.id,
        items=[{"product_id": product.id, "quantity": 1,
                "unit_price": Decimal("150.00"),
                "restock": False, "sent_to_factory": True}],
    )
    SalesService.validate_return(context=admin_context, session=session, return_id=sales_return.id)

    from src.modules.inventory.models import StockLevel
    level = session.query(StockLevel).filter(StockLevel.product_id == product.id).first()
    assert level.quantity == 8  # 10 - 2, nothing restocked


def test_return_cannot_exceed_sold_quantity(session, admin_context):
    """Returning more than was sold on the invoice is forbidden."""
    customer = _make_customer(session)
    invoice, product = _make_validated_invoice(session, admin_context, customer, qty=2)
    with pytest.raises(ValueError, match="only 2 sold"):
        SalesService.create_return(
            context=admin_context, session=session,
            return_number="2026-003", customer_id=customer.id,
            return_type="Refund", invoice_id=invoice.id,
            items=[{"product_id": product.id, "quantity": 5,
                    "unit_price": Decimal("150.00")}],
        )