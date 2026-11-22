from decimal import Decimal

import pytest

from src.modules.accounting.models import AccountType, AccountMovement, MovementDirection
from src.modules.accounting.services import AccountingService
from src.security.permissions import AccessDenied


def _accounts_by_name(context, session):
    return {a["name"]: a for a in AccountingService.list_accounts(context, session=session)}


def test_seeded_payment_methods(session, admin_context):
    methods = AccountingService.list_methods(admin_context, session=session)
    names = {m["name"] for m in methods}
    assert {"Virement bancaire", "Espèce", "TPE", "Chèque", "Versement"} <= names
    cheque = next(m for m in methods if m["name"] == "Chèque")
    assert cheque["requires_reference"] is True


def test_deposit_withdraw_and_running_balance(session, admin_context):
    cash = AccountingService.create_account(
        admin_context, session=session, name="Caisse",
        account_type=AccountType.CASH, opening_balance=Decimal("100.00"),
    )
    AccountingService.deposit(
        admin_context, session=session, account_id=cash.id,
        amount=Decimal("50.50"), description="Vente comptoir",
    )
    AccountingService.withdraw(
        admin_context, session=session, account_id=cash.id,
        amount=Decimal("30.00"), description="Achat fournitures",
    )

    account = _accounts_by_name(admin_context, session)["Caisse"]
    assert account["balance"] == Decimal("120.50")

    ledger = AccountingService.get_ledger(admin_context, session=session, account_id=cash.id)
    assert [row["balance"] for row in ledger["rows"]] == [
        Decimal("150.50"), Decimal("120.50")
    ]


def test_transfer_creates_two_sides(session, admin_context):
    cash = AccountingService.create_account(
        admin_context, session=session, name="Caisse",
        opening_balance=Decimal("200.00"),
    )
    bank = AccountingService.create_account(
        admin_context, session=session, name="Banque",
        account_type=AccountType.BANK,
    )

    AccountingService.transfer_funds(
        admin_context, session=session, from_account_id=cash.id,
        to_account_id=bank.id, amount=Decimal("120.00"),
        reference="REM-1",
    )

    balances = _accounts_by_name(admin_context, session)
    assert balances["Caisse"]["balance"] == Decimal("80.00")
    assert balances["Banque"]["balance"] == Decimal("120.00")

    movements = session.query(AccountMovement).all()
    assert len(movements) == 2
    assert movements[0].transfer_group == movements[1].transfer_group
    assert {m.direction for m in movements} == {MovementDirection.IN, MovementDirection.OUT}


def test_method_requiring_reference_is_enforced(session, admin_context):
    account = AccountingService.create_account(
        admin_context, session=session, name="Caisse"
    )
    cheque = next(
        m for m in AccountingService.list_methods(admin_context, session=session)
        if m["name"] == "Chèque"
    )

    with pytest.raises(ValueError, match="requires a reference"):
        AccountingService.deposit(
            admin_context, session=session, account_id=account.id,
            amount=Decimal("10.00"), description="Chèque client",
            method_id=cheque["id"],
        )

    movement = AccountingService.deposit(
        admin_context, session=session, account_id=account.id,
        amount=Decimal("10.00"), description="Chèque client",
        method_id=cheque["id"], reference="CHQ-42",
    )
    assert movement.reference == "CHQ-42"


def test_non_positive_amount_rejected(session, admin_context):
    account = AccountingService.create_account(
        admin_context, session=session, name="Caisse"
    )
    with pytest.raises(ValueError, match="strictly positive"):
        AccountingService.deposit(
            admin_context, session=session, account_id=account.id,
            amount=Decimal("0"), description="Zero",
        )


def test_permissions_are_enforced(session, unauthorized_context, admin_context):
    with pytest.raises(AccessDenied):
        AccountingService.list_accounts(unauthorized_context, session=session)
    with pytest.raises(AccessDenied):
        AccountingService.create_account(
            unauthorized_context, session=session, name="Caisse"
        )


def test_account_with_balance_cannot_close(session, admin_context):
    account = AccountingService.create_account(
        admin_context, session=session, name="Caisse",
        opening_balance=Decimal("5.00"),
    )
    with pytest.raises(ValueError, match="balance is not zero"):
        AccountingService.set_account_active(
            admin_context, session=session, account_id=account.id, is_active=False
        )

    AccountingService.withdraw(
        admin_context, session=session, account_id=account.id,
        amount=Decimal("5.00"), description="Vidage caisse",
    )
    AccountingService.set_account_active(
        admin_context, session=session, account_id=account.id, is_active=False
    )
    assert AccountingService.list_accounts(admin_context, session=session) == []


def test_opening_balance_locked_after_first_movement(session, admin_context):
    account = AccountingService.create_account(
        admin_context, session=session, name="Caisse"
    )
    AccountingService.deposit(
        admin_context, session=session, account_id=account.id,
        amount=Decimal("1.00"), description="Test",
    )
    with pytest.raises(ValueError, match="opening balance"):
        AccountingService.update_account(
            admin_context, session=session, account_id=account.id,
            opening_balance=Decimal("99.00"),
        )


def test_movements_are_immutable(session, admin_context):
    account = AccountingService.create_account(
        admin_context, session=session, name="Caisse"
    )
    movement = AccountingService.deposit(
        admin_context, session=session, account_id=account.id,
        amount=Decimal("1.00"), description="Test",
    )
    movement.description = "Edited"
    with pytest.raises(ValueError, match="immutable"):
        session.flush()
    session.rollback()


def test_duplicate_account_name_rejected(session, admin_context):
    AccountingService.create_account(admin_context, session=session, name="Caisse")
    with pytest.raises(ValueError, match="already exists"):
        AccountingService.create_account(admin_context, session=session, name="Caisse")
