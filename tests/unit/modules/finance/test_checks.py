import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from src.modules.finance.services import FinanceService
from src.modules.finance.models import Check, CheckDirection, CheckStatus, FinancialJournalEntry, TransactionType
from src.modules.crm.models import Customer
from src.modules.suppliers.models import Supplier
from src.core.context import RequestContext
from src.security.permissions import AccessDenied


@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})


@pytest.fixture
def unauthorized_context():
    return RequestContext(user_id="2", username="guest", role="Guest", permissions=set())


@pytest.fixture
def customer(session):
    c = Customer(company_name="TAZI HOUSE PARTS SARL AU", ice_number="003584281000052")
    session.add(c)
    session.flush()
    return c


@pytest.fixture
def supplier(session):
    s = Supplier(company_name="Valact Consulting")
    session.add(s)
    session.flush()
    return s


# --- Creation ---

def test_create_incoming_check(session, admin_context, customer):
    """Incoming check linked to a customer, starts Pending."""
    due = datetime.now() + timedelta(days=30)
    check = FinanceService.create_check(
        context=admin_context, session=session,
        check_number="1800089", direction="Incoming",
        amount=Decimal("30700.00"), due_date=due,
        party_name=customer.company_name, customer_id=customer.id,
        bank="BMCE",
    )
    assert check.status == CheckStatus.PENDING
    assert check.direction == CheckDirection.INCOMING
    assert check.amount == Decimal("30700.00")


def test_create_check_validation(session, admin_context, customer, supplier):
    """Incoming checks need a customer; outgoing need a supplier; amount > 0."""
    due = datetime.now() + timedelta(days=5)
    with pytest.raises(ValueError, match="linked to a customer"):
        FinanceService.create_check(
            context=admin_context, session=session,
            check_number="X1", direction="Incoming",
            amount=Decimal("100.00"), due_date=due, party_name="Someone",
        )
    with pytest.raises(ValueError, match="linked to a supplier"):
        FinanceService.create_check(
            context=admin_context, session=session,
            check_number="X2", direction="Outgoing",
            amount=Decimal("100.00"), due_date=due, party_name="Someone",
        )
    with pytest.raises(ValueError, match="strictly positive"):
        FinanceService.create_check(
            context=admin_context, session=session,
            check_number="X3", direction="Incoming",
            amount=Decimal("0.00"), due_date=due, party_name="Someone",
            customer_id=customer.id,
        )


def test_create_check_requires_authorization(session, unauthorized_context, customer):
    with pytest.raises(AccessDenied):
        FinanceService.create_check(
            context=unauthorized_context, session=session,
            check_number="X9", direction="Incoming",
            amount=Decimal("100.00"), due_date=datetime.now(),
            party_name="X", customer_id=customer.id,
        )


# --- Status lifecycle ---

def test_check_lifecycle_clear_creates_journal(session, admin_context, customer):
    """Pending -> Deposited -> Cleared, with a journal entry on clearing."""
    due = datetime.now() + timedelta(days=10)
    check = FinanceService.create_check(
        context=admin_context, session=session,
        check_number="1800090", direction="Incoming",
        amount=Decimal("5300.00"), due_date=due,
        party_name=customer.company_name, customer_id=customer.id,
    )
    FinanceService.update_check_status(context=admin_context, session=session, check_id=check.id, new_status="Deposited")
    assert check.status == CheckStatus.DEPOSITED
    FinanceService.update_check_status(context=admin_context, session=session, check_id=check.id, new_status="Cleared")
    assert check.status == CheckStatus.CLEARED

    entries = session.query(FinancialJournalEntry).filter(
        FinancialJournalEntry.reference_id == "CHECK-1800090",
    ).all()
    assert len(entries) == 1
    assert entries[0].amount == Decimal("5300.00")
    assert entries[0].transaction_type == TransactionType.PAYMENT_RECEIVED


def test_check_invalid_transition_rejected(session, admin_context, customer):
    """Pending -> Bounced is not a legal transition."""
    due = datetime.now() + timedelta(days=10)
    check = FinanceService.create_check(
        context=admin_context, session=session,
        check_number="1800091", direction="Incoming",
        amount=Decimal("500.00"), due_date=due,
        party_name=customer.company_name, customer_id=customer.id,
    )
    with pytest.raises(ValueError, match="Cannot move check"):
        FinanceService.update_check_status(context=admin_context, session=session, check_id=check.id, new_status="Bounced")


def test_bounced_check_can_be_redeposited(session, admin_context, customer):
    """Bounced -> Deposited is allowed (second presentation)."""
    due = datetime.now() + timedelta(days=10)
    check = FinanceService.create_check(
        context=admin_context, session=session,
        check_number="1800092", direction="Incoming",
        amount=Decimal("500.00"), due_date=due,
        party_name=customer.company_name, customer_id=customer.id,
    )
    FinanceService.update_check_status(context=admin_context, session=session, check_id=check.id, new_status="Deposited")
    FinanceService.update_check_status(context=admin_context, session=session, check_id=check.id, new_status="Bounced")
    FinanceService.update_check_status(context=admin_context, session=session, check_id=check.id, new_status="Deposited")
    assert check.status == CheckStatus.DEPOSITED


# --- Reminders ---

def test_get_checks_due_within(session, admin_context, customer):
    """Only pending checks due within the horizon are returned, ordered by date."""
    now = datetime.now()
    due_soon = FinanceService.create_check(
        context=admin_context, session=session,
        check_number="D-SOON", direction="Incoming",
        amount=Decimal("100.00"), due_date=now + timedelta(days=3),
        party_name="A", customer_id=customer.id,
    )
    due_late = FinanceService.create_check(
        context=admin_context, session=session,
        check_number="D-LATE", direction="Incoming",
        amount=Decimal("100.00"), due_date=now + timedelta(days=60),
        party_name="B", customer_id=customer.id,
    )
    overdue = FinanceService.create_check(
        context=admin_context, session=session,
        check_number="D-OVER", direction="Incoming",
        amount=Decimal("100.00"), due_date=now - timedelta(days=2),
        party_name="C", customer_id=customer.id,
    )

    due = FinanceService.get_checks_due_within(context=admin_context, session=session, days=7)
    numbers = [c.check_number for c in due]
    assert "D-SOON" in numbers
    assert "D-OVER" in numbers  # overdue included by default
    assert "D-LATE" not in numbers
    # Ordered by due date ascending (overdue first)
    assert numbers.index("D-OVER") < numbers.index("D-SOON")