"""Customer account statement: debit/credit, opening balance, running total."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from src.modules.crm.models import Customer
from src.modules.crm.services import CRMService
from src.modules.sales.models import (
    CustomerDeposit, DepositState, Invoice, InvoiceState, Payment,
    PaymentMethod, SaleChannel,
)
from src.security.permissions import AccessDenied


def _customer(session, name="Client Test SARL", phone="+212600000000"):
    customer = Customer(company_name=name, phone=phone)
    session.add(customer)
    session.flush()
    return customer


def _invoice(session, customer, number, amount, state=InvoiceState.VALIDATED,
             when=None):
    invoice = Invoice(
        invoice_number=number,
        customer_id=customer.id,
        state=state,
        total_amount=Decimal(amount),
        channel=SaleChannel.STORE,
    )
    if when is not None:
        invoice.created_at = when
    session.add(invoice)
    session.flush()
    return invoice


def _payment(session, invoice, amount, when=None, reference=None,
             method=PaymentMethod.CASH):
    payment = Payment(
        invoice_id=invoice.id,
        method=method,
        amount=Decimal(amount),
        reference=reference,
    )
    if when is not None:
        payment.created_at = when
    session.add(payment)
    session.flush()
    return payment


def _deposit(session, customer, number, amount, when=None):
    deposit = CustomerDeposit(
        deposit_number=number,
        customer_id=customer.id,
        amount=Decimal(amount),
        amount_used=Decimal("0.00"),
        state=DepositState.OPEN,
        method=PaymentMethod.CASH,
    )
    if when is not None:
        deposit.created_at = when
    session.add(deposit)
    session.flush()
    return deposit


def test_statement_combines_invoices_payments_and_deposits(session, admin_context):
    customer = _customer(session)
    invoice = _invoice(session, customer, "F-1", "1000.00")
    _payment(session, invoice, "400.00", reference="VIR-1",
             method=PaymentMethod.TRANSFER)
    _deposit(session, customer, "BON-1", "300.00")

    statement = CRMService.get_customer_statement(
        admin_context, session=session, customer_id=customer.id
    )

    assert statement["party"]["name"] == "Client Test SARL"
    assert statement["opening_balance"] == Decimal("0.00")
    assert statement["total_debit"] == Decimal("1000.00")
    assert statement["total_credit"] == Decimal("700.00")
    assert statement["closing_balance"] == Decimal("300.00")
    # Invoice first, then money received, each line updating the balance.
    assert [row["type"] for row in statement["rows"]] == [
        "Invoice", "Payment", "Deposit",
    ]
    assert [row["balance"] for row in statement["rows"]] == [
        Decimal("1000.00"), Decimal("600.00"), Decimal("300.00"),
    ]


def test_deposit_allocation_payment_is_not_credited_twice(session, admin_context):
    """Applying a deposit stamps its number on the payment: that line is not new money."""
    customer = _customer(session)
    invoice = _invoice(session, customer, "F-2", "800.00")
    _deposit(session, customer, "BON-2", "500.00")
    _payment(session, invoice, "500.00", reference="BON-2")

    statement = CRMService.get_customer_statement(
        admin_context, session=session, customer_id=customer.id
    )

    assert statement["total_credit"] == Decimal("500.00")
    assert statement["closing_balance"] == Decimal("300.00")
    assert len(statement["rows"]) == 2  # invoice + deposit, no allocation line


def test_statement_folds_earlier_movements_into_the_opening_balance(session, admin_context):
    customer = _customer(session)
    old_invoice = _invoice(session, customer, "F-OLD", "1000.00",
                           when=datetime(2026, 1, 5, 9, 0))
    _payment(session, old_invoice, "400.00", when=datetime(2026, 1, 10, 9, 0))
    _invoice(session, customer, "F-NEW", "200.00", when=datetime(2026, 2, 5, 14, 30))

    statement = CRMService.get_customer_statement(
        admin_context, session=session, customer_id=customer.id,
        date_from=date(2026, 2, 1), date_to=date(2026, 2, 28),
    )

    assert statement["opening_balance"] == Decimal("600.00")
    assert len(statement["rows"]) == 1
    assert statement["rows"][0]["document"] == "F-NEW"
    assert statement["closing_balance"] == Decimal("800.00")


def test_statement_includes_movements_on_the_last_day(session, admin_context):
    customer = _customer(session)
    _invoice(session, customer, "F-LAST", "150.00",
             when=datetime(2026, 3, 31, 23, 45))

    statement = CRMService.get_customer_statement(
        admin_context, session=session, customer_id=customer.id,
        date_from=date(2026, 3, 1), date_to=date(2026, 3, 31),
    )

    assert len(statement["rows"]) == 1
    assert statement["closing_balance"] == Decimal("150.00")


def test_draft_invoices_are_not_part_of_the_statement(session, admin_context):
    customer = _customer(session)
    _invoice(session, customer, "F-DRAFT", "999.00", state=InvoiceState.DRAFT)

    statement = CRMService.get_customer_statement(
        admin_context, session=session, customer_id=customer.id
    )

    assert statement["rows"] == []
    assert statement["closing_balance"] == Decimal("0.00")


def test_statement_rejects_a_reversed_period(session, admin_context):
    customer = _customer(session)
    with pytest.raises(ValueError, match="start date"):
        CRMService.get_customer_statement(
            admin_context, session=session, customer_id=customer.id,
            date_from=date(2026, 3, 31), date_to=date(2026, 3, 1),
        )


def test_statement_unknown_customer_raises(session, admin_context):
    with pytest.raises(ValueError, match="not found"):
        CRMService.get_customer_statement(
            admin_context, session=session, customer_id=999
        )


def test_statement_requires_the_view_permission(session, unauthorized_context):
    with pytest.raises(AccessDenied):
        CRMService.get_customer_statement(
            unauthorized_context, session=session, customer_id=1
        )
