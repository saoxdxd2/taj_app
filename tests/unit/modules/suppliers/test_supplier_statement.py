"""Supplier account statement: validated purchases, terms-based due dates."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from src.modules.purchasing.models import Purchase, PurchaseState
from src.modules.suppliers.models import Supplier
from src.modules.suppliers.services import SupplierService
from src.security.permissions import AccessDenied


def _supplier(session, name="Fournisseur Test", phone="+212611111111",
              payment_terms_days=30):
    supplier = Supplier(
        company_name=name, phone=phone, payment_terms_days=payment_terms_days
    )
    session.add(supplier)
    session.flush()
    return supplier


def _purchase(session, supplier, reference, amount,
              state=PurchaseState.VALIDATED, when=None):
    purchase = Purchase(
        reference=reference,
        supplier_id=supplier.id,
        state=state,
        total_amount=Decimal(amount),
    )
    if when is not None:
        purchase.created_at = when
    session.add(purchase)
    session.flush()
    return purchase


def test_statement_lists_validated_purchases_with_due_dates(session, admin_context):
    supplier = _supplier(session, payment_terms_days=30)
    created = datetime(2026, 5, 1, 10, 0)
    _purchase(session, supplier, "ACH-1", "1200.00", when=created)

    statement = SupplierService.get_supplier_statement(
        admin_context, session=session, supplier_id=supplier.id
    )

    assert statement["party"]["name"] == "Fournisseur Test"
    assert statement["total_debit"] == Decimal("1200.00")
    assert statement["closing_balance"] == Decimal("1200.00")
    assert statement["rows"][0]["due_date"] == created + timedelta(days=30)


def test_draft_purchases_and_prior_balances_respect_the_period(session, admin_context):
    supplier = _supplier(session, payment_terms_days=0)
    _purchase(session, supplier, "ACH-OLD", "500.00",
              when=datetime(2026, 1, 5, 9, 0))
    _purchase(session, supplier, "ACH-NEW", "250.00",
              when=datetime(2026, 2, 5, 9, 0))
    _purchase(session, supplier, "ACH-DRAFT", "999.00",
              state=PurchaseState.DRAFT, when=datetime(2026, 2, 6, 9, 0))

    statement = SupplierService.get_supplier_statement(
        admin_context, session=session, supplier_id=supplier.id,
        date_from=date(2026, 2, 1), date_to=date(2026, 2, 28),
    )

    assert statement["opening_balance"] == Decimal("500.00")
    assert len(statement["rows"]) == 1
    assert statement["rows"][0]["document"] == "ACH-NEW"
    assert statement["rows"][0]["due_date"] is None  # cash terms
    assert statement["closing_balance"] == Decimal("750.00")


def test_supplier_statement_unknown_supplier_raises(session, admin_context):
    with pytest.raises(ValueError, match="not found"):
        SupplierService.get_supplier_statement(
            admin_context, session=session, supplier_id=999
        )


def test_supplier_statement_requires_the_view_permission(session, unauthorized_context):
    with pytest.raises(AccessDenied):
        SupplierService.get_supplier_statement(
            unauthorized_context, session=session, supplier_id=1
        )
