import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.modules.sales.services import SalesService
from src.modules.sales.models import (
    Invoice, InvoiceItem, InvoiceState, Payment, PaymentMethod,
    CustomerDeposit, DepositState, SalesReturn, ReturnItem, ReturnType,
    ReturnState,
)
from src.modules.inventory.services import InventoryService
from src.modules.finance.services import FinanceService
from src.modules.finance.models import FinancialJournalEntry, TransactionType
from src.modules.crm.models import Customer
from src.security.permissions import AccessDenied
from src.dto.sales_dto import InvoiceItemCreateDTO
from pydantic import ValidationError


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


# --- DTO validation layer ---

def test_add_item_accepts_a_validated_dto(session, admin_context):
    """The DTO path is equivalent to passing primitives."""
    customer = _make_customer(session)
    product = _make_stocked_product(session, admin_context, "DTO-01")
    invoice = SalesService.create_invoice_draft(
        context=admin_context, session=session, customer_id=customer.id,
    )
    item = SalesService.add_item_to_invoice(
        context=admin_context, session=session,
        dto=InvoiceItemCreateDTO(
            invoice_id=invoice.id,
            product_id=product.id,
            quantity=2,
            unit_price=Decimal("150.00"),
            vat_rate=Decimal("20.00"),
        ),
    )
    assert item.quantity == 2
    assert item.warranty_months == 12
    # 2 x 150.00 incl. 20% VAT = 360.00
    assert invoice.total_amount == Decimal("360.00")


def test_add_item_dto_validates_before_querying_the_database(session, admin_context):
    """Invalid DTO input fails on validation, not on a missing invoice row."""
    with pytest.raises(ValidationError):
        SalesService.add_item_to_invoice(
            context=admin_context, session=session,
            dto=InvoiceItemCreateDTO(
                invoice_id=999, product_id=1,
                quantity=0, unit_price=Decimal("150.00"), vat_rate=Decimal("20.00"),
            ),
        )


def test_add_item_primitive_path_keeps_legacy_error_messages(session, admin_context):
    """The primitive path still raises the ValueError messages it always did."""
    customer = _make_customer(session)
    invoice = SalesService.create_invoice_draft(
        context=admin_context, session=session, customer_id=customer.id,
    )
    with pytest.raises(ValueError, match="Quantity must be positive"):
        SalesService.add_item_to_invoice(
            context=admin_context, session=session, invoice_id=invoice.id,
            product_id=1, quantity=0,
            unit_price=Decimal("150.00"), vat_rate=Decimal("20.00"),
        )
    with pytest.raises(ValueError, match="Unit cost cannot be negative"):
        SalesService.add_item_to_invoice(
            context=admin_context, session=session, invoice_id=invoice.id,
            product_id=1, quantity=1,
            unit_price=Decimal("150.00"), vat_rate=Decimal("20.00"),
            unit_cost=Decimal("-1.00"),
        )


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


def _make_check(session, admin_context, customer, amount="360.00",
                number="1800089", direction="Incoming"):
    return FinanceService.create_check(
        context=admin_context, session=session,
        check_number=number, direction=direction,
        amount=Decimal(amount), due_date=datetime.now(),
        party_name=customer.company_name, customer_id=customer.id,
    )


def test_payment_check_defers_journal(session, admin_context):
    """Check payments create a Payment but NO journal entry until the check clears."""
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    check = _make_check(session, admin_context, customer)
    SalesService.register_payment(
        context=admin_context, session=session, invoice_id=invoice.id,
        method="Check", amount=Decimal("360.00"), reference="1800089",
        check_id=check.id,
    )
    assert invoice.state == InvoiceState.PAID
    entries = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.transaction_type == TransactionType.PAYMENT_RECEIVED,
        FinancialJournalEntry.reference_id == f"INV-{invoice.invoice_number}",
    ).all()
    assert len(entries) == 0  # deferred until check clears

    # Clearing the linked check is what posts the money.
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Cleared",
    )
    check_entries = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == "CHECK-1800089"
    ).all()
    assert len(check_entries) == 1
    assert check_entries[0].amount == Decimal("360.00")


def test_cleared_unused_check_settles_invoice_without_double_journal(
    session, admin_context
):
    """A receipt that cleared before being allocated can still settle an invoice."""
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    check = _make_check(
        session, admin_context, customer, number="CLEAR-EARLY-1"
    )
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Deposited",
    )
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Cleared",
    )
    entries_before = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == "CHECK-CLEAR-EARLY-1"
    ).count()
    assert entries_before == 1

    SalesService.register_payment(
        context=admin_context, session=session, invoice_id=invoice.id,
        method="Check", amount=Decimal("360.00"), check_id=check.id,
    )

    assert invoice.state == InvoiceState.PAID
    entries_after = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == "CHECK-CLEAR-EARLY-1"
    ).count()
    assert entries_after == 1  # allocation only; no second receipt


def test_check_payment_requires_a_registered_check(session, admin_context):
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    with pytest.raises(ValueError, match="must reference a check"):
        SalesService.register_payment(
            context=admin_context, session=session, invoice_id=invoice.id,
            method="Check", amount=Decimal("360.00"), reference="1800089",
        )


def test_check_payment_cannot_reuse_another_customers_check(session, admin_context):
    customer = _make_customer(session)
    other = _make_customer(session, name="Other Client")
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    check = _make_check(session, admin_context, other)

    with pytest.raises(ValueError, match="does not belong"):
        SalesService.register_payment(
            context=admin_context, session=session, invoice_id=invoice.id,
            method="Check", amount=Decimal("360.00"), check_id=check.id,
        )


def test_check_payment_amount_must_match_the_check(session, admin_context):
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    check = _make_check(session, admin_context, customer, amount="300.00")

    with pytest.raises(ValueError, match="They must match"):
        SalesService.register_payment(
            context=admin_context, session=session, invoice_id=invoice.id,
            method="Check", amount=Decimal("360.00"), check_id=check.id,
        )


def test_check_payment_cannot_be_linked_twice(session, admin_context):
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    check = _make_check(session, admin_context, customer)

    SalesService.register_payment(
        context=admin_context, session=session, invoice_id=invoice.id,
        method="Check", amount=Decimal("360.00"), check_id=check.id,
    )
    # A second, separate invoice of the same amount must not reuse the paper.
    invoice2, _ = _make_validated_invoice(
        session, admin_context, customer, sku="CLI-02"
    )
    with pytest.raises(ValueError, match="already linked"):
        SalesService.register_payment(
            context=admin_context, session=session, invoice_id=invoice2.id,
            method="Check", amount=Decimal("360.00"), check_id=check.id,
        )


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


def test_deposit_cannot_pay_another_customers_invoice(session, admin_context):
    """A bon belongs to the customer who paid it; it cannot settle another account."""
    customer = _make_customer(session)
    other = _make_customer(session, name="Other Client")
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    deposit = SalesService.create_deposit(
        context=admin_context, session=session,
        deposit_number="BON-OTHER-1", customer_id=other.id,
        amount=Decimal("300.00"), method="Cash",
    )

    with pytest.raises(ValueError, match="different customer"):
        SalesService.apply_deposit_to_invoice(
            context=admin_context, session=session,
            deposit_id=deposit.id, invoice_id=invoice.id,
            amount=Decimal("300.00"),
        )
    assert deposit.amount_used == Decimal("0.00")


def test_payments_and_deposits_work_with_autoflush_disabled(db_engine, admin_context):
    """Production uses autoflush=False; service methods must flush explicitly."""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = Session()
    try:
        customer = _make_customer(session)
        invoice, _ = _make_validated_invoice(session, admin_context, customer)

        deposit = SalesService.create_deposit(
            context=admin_context, session=session,
            deposit_number="BON-NO-AF", customer_id=customer.id,
            amount=Decimal("100.00"), method="Cash",
        )
        assert deposit.id is not None

        payment = SalesService.register_payment(
            context=admin_context, session=session,
            invoice_id=invoice.id, method="Cash",
            amount=invoice.total_amount,
        )
        assert payment.id is not None
        assert invoice.state == InvoiceState.PAID
    finally:
        session.rollback()
        session.close()


def test_check_deposit_is_linked_and_not_reusable(session, admin_context):
    customer = _make_customer(session)
    check = _make_check(
        session, admin_context, customer, amount="500.00", number="DEP-CHK-1"
    )
    deposit = SalesService.create_deposit(
        context=admin_context, session=session,
        deposit_number="BON-CHK-1", customer_id=customer.id,
        amount=Decimal("500.00"), method="Check", check_id=check.id,
    )
    assert deposit.check_id == check.id
    # No journal entry until the check clears.
    entries = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == "BON-CHK-1"
    ).all()
    assert entries == []

    with pytest.raises(ValueError, match="already linked"):
        SalesService.create_deposit(
            context=admin_context, session=session,
            deposit_number="BON-CHK-2", customer_id=customer.id,
            amount=Decimal("500.00"), method="Check", check_id=check.id,
        )
    with pytest.raises(ValueError, match="must reference a check"):
        SalesService.create_deposit(
            context=admin_context, session=session,
            deposit_number="BON-CHK-3", customer_id=customer.id,
            amount=Decimal("500.00"), method="Check",
        )


def test_bounced_check_deposit_cannot_be_applied(session, admin_context):
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    check = _make_check(
        session, admin_context, customer, amount="360.00", number="DEP-CHK-2"
    )
    deposit = SalesService.create_deposit(
        context=admin_context, session=session,
        deposit_number="BON-CHK-4", customer_id=customer.id,
        amount=Decimal("360.00"), method="Check", check_id=check.id,
    )
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Deposited",
    )
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Bounced",
    )

    # Bouncing the check cancels the deposit outright, so it cannot be used.
    with pytest.raises(ValueError, match="Deposit is not open"):
        SalesService.apply_deposit_to_invoice(
            context=admin_context, session=session,
            deposit_id=deposit.id, invoice_id=invoice.id,
            amount=Decimal("360.00"),
        )


def test_bounced_check_reopens_invoice_and_removes_payment(session, admin_context):
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    check = _make_check(session, admin_context, customer)
    SalesService.register_payment(
        context=admin_context, session=session, invoice_id=invoice.id,
        method="Check", amount=Decimal("360.00"), check_id=check.id,
    )
    assert invoice.state == InvoiceState.PAID

    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Deposited",
    )
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Bounced",
    )

    assert invoice.state == InvoiceState.VALIDATED
    assert session.query(Payment).filter(Payment.check_id == check.id).count() == 0
    assert SalesService.get_invoice_balance(
        context=admin_context, invoice_id=invoice.id, session=session
    ) == Decimal("360.00")
    # A check that never cleared must not post a journal entry.
    assert session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == "CHECK-1800089"
    ).count() == 0


def test_bounced_check_cancels_deposit_and_reopens_invoice(session, admin_context):
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    check = _make_check(
        session, admin_context, customer, number="DEP-BOUNCE-1"
    )
    deposit = SalesService.create_deposit(
        context=admin_context, session=session,
        deposit_number="BON-BOUNCE-1", customer_id=customer.id,
        amount=Decimal("360.00"), method="Check", check_id=check.id,
    )
    session.flush()  # assign the deposit id in tests (production commits)
    SalesService.apply_deposit_to_invoice(
        context=admin_context, session=session,
        deposit_id=deposit.id, invoice_id=invoice.id,
        amount=Decimal("360.00"),
    )
    assert invoice.state == InvoiceState.PAID
    assert deposit.state == DepositState.SETTLED

    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Deposited",
    )
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Bounced",
    )

    assert deposit.state == DepositState.CANCELLED
    assert deposit.amount_used == Decimal("0.00")
    assert deposit.check_id is None  # the cured check may be reused
    assert invoice.state == InvoiceState.VALIDATED
    assert session.query(Payment).filter(Payment.check_id == check.id).count() == 0
    assert SalesService.get_invoice_balance(
        context=admin_context, invoice_id=invoice.id, session=session
    ) == Decimal("360.00")


def test_cured_check_can_back_a_new_deposit_after_bounce(session, admin_context):
    """Bouncing releases the paper; a successful second presentation works."""
    customer = _make_customer(session)
    invoice, _ = _make_validated_invoice(session, admin_context, customer)
    check = _make_check(
        session, admin_context, customer, number="CURED-1"
    )
    first = SalesService.create_deposit(
        context=admin_context, session=session,
        deposit_number="BON-CURED-1", customer_id=customer.id,
        amount=Decimal("360.00"), method="Check", check_id=check.id,
    )
    session.flush()
    SalesService.apply_deposit_to_invoice(
        context=admin_context, session=session,
        deposit_id=first.id, invoice_id=invoice.id, amount=Decimal("360.00"),
    )
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Deposited",
    )
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Bounced",
    )
    assert first.state == DepositState.CANCELLED
    assert first.check_id is None
    assert invoice.state == InvoiceState.VALIDATED

    # Second presentation: the same check can back a fresh deposit.
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Deposited",
    )
    second = SalesService.create_deposit(
        context=admin_context, session=session,
        deposit_number="BON-CURED-2", customer_id=customer.id,
        amount=Decimal("360.00"), method="Check", check_id=check.id,
    )
    session.flush()
    SalesService.apply_deposit_to_invoice(
        context=admin_context, session=session,
        deposit_id=second.id, invoice_id=invoice.id, amount=Decimal("360.00"),
    )
    assert invoice.state == InvoiceState.PAID
    FinanceService.update_check_status(
        context=admin_context, session=session,
        check_id=check.id, new_status="Cleared",
    )
    entries = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == "CHECK-CURED-1"
    ).all()
    assert len(entries) == 1  # exactly one receipt, on the successful clearing


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


def test_return_cannot_reuse_quantity_from_a_previous_return(
    session, admin_context
):
    """Two returns cannot refund the same unit twice."""
    customer = _make_customer(session)
    invoice, product = _make_validated_invoice(session, admin_context, customer, qty=2)

    first = SalesService.create_return(
        context=admin_context, session=session,
        return_number="2026-004", customer_id=customer.id,
        return_type="Refund", invoice_id=invoice.id,
        items=[{"product_id": product.id, "quantity": 2,
                "unit_price": Decimal("150.00")}],
    )
    SalesService.validate_return(
        context=admin_context, session=session, return_id=first.id
    )

    with pytest.raises(ValueError, match="only 0 sold"):
        SalesService.create_return(
            context=admin_context, session=session,
            return_number="2026-005", customer_id=customer.id,
            return_type="Refund", invoice_id=invoice.id,
            items=[{"product_id": product.id, "quantity": 1,
                    "unit_price": Decimal("150.00")}],
        )


def test_return_cannot_exceed_quantity_within_one_document(
    session, admin_context
):
    """Duplicate lines in one return must not bypass the sold-quantity check."""
    customer = _make_customer(session)
    invoice, product = _make_validated_invoice(session, admin_context, customer, qty=2)

    with pytest.raises(ValueError, match="only 0 sold"):
        SalesService.create_return(
            context=admin_context, session=session,
            return_number="2026-006", customer_id=customer.id,
            return_type="Refund", invoice_id=invoice.id,
            items=[
                {"product_id": product.id, "quantity": 2,
                 "unit_price": Decimal("150.00")},
                {"product_id": product.id, "quantity": 1,
                 "unit_price": Decimal("150.00")},
            ],
        )


def test_return_customer_must_match_the_invoice(session, admin_context):
    """A return cannot be filed against another customer's invoice."""
    customer = _make_customer(session)
    other = _make_customer(session, name="Other Client")
    invoice, product = _make_validated_invoice(session, admin_context, customer, qty=2)

    with pytest.raises(ValueError, match="does not match the invoice"):
        SalesService.create_return(
            context=admin_context, session=session,
            return_number="2026-007", customer_id=other.id,
            return_type="Refund", invoice_id=invoice.id,
            items=[{"product_id": product.id, "quantity": 1,
                    "unit_price": Decimal("150.00")}],
        )


def test_validate_return_rechecks_remaining_quantity(session, admin_context):
    """A legacy/parallel draft cannot be validated into an over-refund."""
    customer = _make_customer(session)
    invoice, product = _make_validated_invoice(session, admin_context, customer, qty=1)

    first = SalesService.create_return(
        context=admin_context, session=session,
        return_number="2026-008", customer_id=customer.id,
        return_type="Refund", invoice_id=invoice.id,
        items=[{"product_id": product.id, "quantity": 1,
                "unit_price": Decimal("150.00")}],
    )

    # Simulate a draft created before the cumulative check existed.
    legacy = SalesReturn(
        return_number="2026-LEGACY", invoice_id=invoice.id,
        customer_id=customer.id, return_type=ReturnType.REFUND,
        state=ReturnState.DRAFT, total_amount=Decimal("150.00"),
    )
    session.add(legacy)
    session.flush()
    session.add(ReturnItem(
        return_id=legacy.id, product_id=product.id, quantity=1,
        unit_price=Decimal("150.00"),
    ))
    session.flush()

    SalesService.validate_return(
        context=admin_context, session=session, return_id=first.id
    )
    with pytest.raises(ValueError, match="remain returnable"):
        SalesService.validate_return(
            context=admin_context, session=session, return_id=legacy.id
        )