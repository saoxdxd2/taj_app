"""Cash/bank accounts, configurable payment methods and the account ledger.

Every write goes through this service so the same invariants hold no
matter which screen calls it: positive amounts, an active destination
account, a reference when the payment method requires one, and double
entries for transfers.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Union

from sqlalchemy import event, func

from src.core.context import RequestContext
from src.database.transaction import transactional
from src.modules.accounting.models import (
    AccountMovement, AccountType, MovementDirection, MovementType,
    PaymentAccount, PaymentMethodOption,
)
from src.security.permissions import AccessDenied, PermissionManager

logger = logging.getLogger(__name__)


def _utc_naive(value: Union[datetime, date, None]) -> datetime:
    """Normalizes a UI date/datetime to the naive UTC stored in SQLite."""
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    return datetime.combine(value, time.min)


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Amount must be a valid number.")


def _account_type(value) -> AccountType:
    if isinstance(value, AccountType):
        return value
    try:
        return AccountType(value)
    except ValueError:
        try:
            return AccountType[str(value).upper()]
        except KeyError:
            raise ValueError("Account type must be Cash or Bank.")


class AccountingService:
    """Accounts, payment methods and append-only account movements."""

    PERM_ACCOUNTS_VIEW = "Accounting.Accounts.View"
    PERM_ACCOUNTS_MANAGE = "Accounting.Accounts.Manage"
    PERM_METHODS_VIEW = "Accounting.Methods.View"
    PERM_METHODS_MANAGE = "Accounting.Methods.Manage"

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    @staticmethod
    def _require(context: Optional[RequestContext], permission: str) -> None:
        if context is None:
            raise AccessDenied("Authentication is required for this operation.")
        PermissionManager.verify_permission(context, permission)

    @staticmethod
    def _balance_map(session, account_ids: Optional[List[int]] = None) -> Dict[int, Decimal]:
        query = (
            session.query(
                AccountMovement.account_id,
                AccountMovement.direction,
                func.sum(AccountMovement.amount),
            )
            .group_by(AccountMovement.account_id, AccountMovement.direction)
        )
        if account_ids is not None:
            if not account_ids:
                return {}
            query = query.filter(AccountMovement.account_id.in_(account_ids))

        balances: Dict[int, Decimal] = {}
        for account_id, direction, total in query.all():
            signed = Decimal(total or 0)
            if direction == MovementDirection.OUT:
                signed = -signed
            balances[account_id] = balances.get(account_id, Decimal("0.00")) + signed
        return balances

    @classmethod
    def _account_balance(cls, session, account: PaymentAccount) -> Decimal:
        movement_total = cls._balance_map(session, [account.id]).get(
            account.id, Decimal("0.00")
        )
        return Decimal(account.opening_balance or 0) + movement_total

    # ------------------------------------------------------------------
    # Payment accounts
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def list_accounts(context: RequestContext, session,
                      include_inactive: bool = False) -> List[dict]:
        AccountingService._require(context, AccountingService.PERM_ACCOUNTS_VIEW)

        query = session.query(PaymentAccount).order_by(
            PaymentAccount.account_type, PaymentAccount.name
        )
        if not include_inactive:
            query = query.filter(PaymentAccount.is_active.is_(True))
        accounts = query.all()

        movements = AccountingService._balance_map(session, [a.id for a in accounts])
        result = []
        for account in accounts:
            balance = (
                Decimal(account.opening_balance or 0)
                + movements.get(account.id, Decimal("0.00"))
            )
            result.append({
                "id": account.id,
                "name": account.name,
                "account_number": account.account_number or "",
                "bank": account.bank or "",
                "type": account.account_type,
                "opening_balance": Decimal(account.opening_balance or 0),
                "balance": balance,
                "is_active": bool(account.is_active),
            })
        return result

    @staticmethod
    @transactional
    def get_account(context: RequestContext, session, account_id: int) -> dict:
        AccountingService._require(context, AccountingService.PERM_ACCOUNTS_VIEW)
        account = session.get(PaymentAccount, account_id)
        if account is None:
            raise ValueError("Account not found.")
        has_movements = session.query(AccountMovement).filter(
            AccountMovement.account_id == account.id
        ).first() is not None
        return {
            "id": account.id,
            "name": account.name,
            "account_number": account.account_number or "",
            "bank": account.bank or "",
            "type": account.account_type,
            "opening_balance": Decimal(account.opening_balance or 0),
            "balance": AccountingService._account_balance(session, account),
            "is_active": bool(account.is_active),
            "has_movements": has_movements,
        }

    @staticmethod
    @transactional
    def create_account(context: RequestContext, session, name: str,
                       account_type: Union[str, AccountType] = AccountType.CASH,
                       opening_balance=Decimal("0.00"),
                       account_number: Optional[str] = None,
                       bank: Optional[str] = None) -> PaymentAccount:
        AccountingService._require(context, AccountingService.PERM_ACCOUNTS_MANAGE)

        name = (name or "").strip()
        if not name:
            raise ValueError("Account name is required.")
        if session.query(PaymentAccount).filter(PaymentAccount.name == name).first():
            raise ValueError(f"Account '{name}' already exists.")

        account = PaymentAccount(
            name=name,
            account_type=_account_type(account_type),
            opening_balance=_to_decimal(opening_balance),
            account_number=(account_number or "").strip() or None,
            bank=(bank or "").strip() or None,
            is_active=True,
        )
        session.add(account)
        session.flush()
        logger.info(f"Created payment account '{name}' ({account.account_type.value}).")
        return account

    @staticmethod
    @transactional
    def update_account(context: RequestContext, session, account_id: int, *,
                       name: Optional[str] = None,
                       account_type: Optional[Union[str, AccountType]] = None,
                       opening_balance=None,
                       account_number: Optional[str] = None,
                       bank: Optional[str] = None) -> PaymentAccount:
        AccountingService._require(context, AccountingService.PERM_ACCOUNTS_MANAGE)

        account = session.get(PaymentAccount, account_id)
        if account is None:
            raise ValueError("Account not found.")

        if name is not None and name.strip() and name.strip() != account.name:
            new_name = name.strip()
            if session.query(PaymentAccount).filter(PaymentAccount.name == new_name).first():
                raise ValueError(f"Account '{new_name}' already exists.")
            account.name = new_name
        if account_type is not None:
            account.account_type = _account_type(account_type)
        if opening_balance is not None:
            if session.query(AccountMovement).filter(
                AccountMovement.account_id == account.id
            ).first():
                raise ValueError(
                    "The opening balance can only be changed before the first movement."
                )
            account.opening_balance = _to_decimal(opening_balance)
        if account_number is not None:
            account.account_number = account_number.strip() or None
        if bank is not None:
            account.bank = bank.strip() or None

        session.flush()
        return account

    @staticmethod
    @transactional
    def set_account_active(context: RequestContext, session, account_id: int,
                           is_active: bool) -> PaymentAccount:
        AccountingService._require(context, AccountingService.PERM_ACCOUNTS_MANAGE)

        account = session.get(PaymentAccount, account_id)
        if account is None:
            raise ValueError("Account not found.")

        if not is_active and AccountingService._account_balance(session, account) != 0:
            raise ValueError(
                "Cannot close an account whose balance is not zero. "
                "Transfer or withdraw the remaining money first."
            )

        account.is_active = bool(is_active)
        session.flush()
        logger.info(f"Account '{account.name}' {'activated' if is_active else 'closed'}.")
        return account

    # ------------------------------------------------------------------
    # Payment methods
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def list_methods(context: RequestContext, session,
                     include_inactive: bool = False) -> List[dict]:
        AccountingService._require(context, AccountingService.PERM_METHODS_VIEW)

        query = session.query(PaymentMethodOption).order_by(
            PaymentMethodOption.sort_order, PaymentMethodOption.name
        )
        if not include_inactive:
            query = query.filter(PaymentMethodOption.is_active.is_(True))
        methods = query.all()

        accounts = {
            a.id: a.name for a in session.query(PaymentAccount).all()
        }
        return [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description or "",
                "requires_reference": bool(m.requires_reference),
                "deposit_account_id": m.deposit_account_id,
                "deposit_account_name": accounts.get(m.deposit_account_id, ""),
                "withdrawal_account_id": m.withdrawal_account_id,
                "withdrawal_account_name": accounts.get(m.withdrawal_account_id, ""),
                "is_active": bool(m.is_active),
                "sort_order": m.sort_order,
            }
            for m in methods
        ]

    @staticmethod
    @transactional
    def create_method(context: RequestContext, session, name: str,
                      description: Optional[str] = None,
                      requires_reference: bool = False,
                      deposit_account_id: Optional[int] = None,
                      withdrawal_account_id: Optional[int] = None,
                      sort_order: int = 0) -> PaymentMethodOption:
        AccountingService._require(context, AccountingService.PERM_METHODS_MANAGE)

        name = (name or "").strip()
        if not name:
            raise ValueError("Payment method name is required.")
        if session.query(PaymentMethodOption).filter(
            PaymentMethodOption.name == name
        ).first():
            raise ValueError(f"Payment method '{name}' already exists.")

        method = PaymentMethodOption(
            name=name,
            description=(description or "").strip() or None,
            requires_reference=bool(requires_reference),
            deposit_account_id=deposit_account_id,
            withdrawal_account_id=withdrawal_account_id,
            sort_order=int(sort_order or 0),
            is_active=True,
        )
        session.add(method)
        session.flush()
        return method

    @staticmethod
    @transactional
    def update_method(context: RequestContext, session, method_id: int, *,
                      name: Optional[str] = None,
                      description: Optional[str] = None,
                      requires_reference: Optional[bool] = None,
                      deposit_account_id: Optional[int] = None,
                      withdrawal_account_id: Optional[int] = None,
                      sort_order: Optional[int] = None) -> PaymentMethodOption:
        AccountingService._require(context, AccountingService.PERM_METHODS_MANAGE)

        method = session.get(PaymentMethodOption, method_id)
        if method is None:
            raise ValueError("Payment method not found.")

        if name is not None and name.strip() and name.strip() != method.name:
            new_name = name.strip()
            if session.query(PaymentMethodOption).filter(
                PaymentMethodOption.name == new_name
            ).first():
                raise ValueError(f"Payment method '{new_name}' already exists.")
            method.name = new_name
        if description is not None:
            method.description = description.strip() or None
        if requires_reference is not None:
            method.requires_reference = bool(requires_reference)
        if deposit_account_id is not None:
            method.deposit_account_id = deposit_account_id or None
        if withdrawal_account_id is not None:
            method.withdrawal_account_id = withdrawal_account_id or None
        if sort_order is not None:
            method.sort_order = int(sort_order)

        session.flush()
        return method

    @staticmethod
    @transactional
    def set_method_active(context: RequestContext, session, method_id: int,
                          is_active: bool) -> PaymentMethodOption:
        AccountingService._require(context, AccountingService.PERM_METHODS_MANAGE)

        method = session.get(PaymentMethodOption, method_id)
        if method is None:
            raise ValueError("Payment method not found.")
        method.is_active = bool(is_active)
        session.flush()
        return method

    # ------------------------------------------------------------------
    # Movements
    # ------------------------------------------------------------------

    @staticmethod
    def _build_movement(context: RequestContext, session, *, account: PaymentAccount,
                        direction: MovementDirection, amount, movement_type: MovementType,
                        description: str, reference: Optional[str],
                        method_id: Optional[int], movement_date,
                        transfer_group: Optional[str] = None) -> AccountMovement:
        if not account.is_active:
            raise ValueError(f"Account '{account.name}' is closed.")

        value = _to_decimal(amount)
        if value <= 0:
            raise ValueError("Amount must be strictly positive.")

        description = (description or "").strip()
        if not description:
            raise ValueError("A description is required for every movement.")

        reference = (reference or "").strip() or None
        if method_id is not None:
            method = session.get(PaymentMethodOption, method_id)
            if method is None or not method.is_active:
                raise ValueError("The selected payment method is not available.")
            if method.requires_reference and not reference:
                raise ValueError(
                    f"Payment method '{method.name}' requires a reference."
                )

        user_id = None
        if context.user_id:
            try:
                user_id = int(context.user_id)
            except (TypeError, ValueError):
                user_id = None

        return AccountMovement(
            account_id=account.id,
            direction=direction,
            amount=value,
            movement_date=_utc_naive(movement_date),
            movement_type=movement_type,
            method_id=method_id,
            reference=reference,
            description=description,
            transfer_group=transfer_group,
            user_id=user_id,
        )

    @staticmethod
    @transactional
    def deposit(context: RequestContext, session, account_id: int, amount,
                description: str, method_id: Optional[int] = None,
                reference: Optional[str] = None,
                movement_date=None) -> AccountMovement:
        AccountingService._require(context, AccountingService.PERM_ACCOUNTS_MANAGE)
        account = session.get(PaymentAccount, account_id)
        if account is None:
            raise ValueError("Account not found.")

        movement = AccountingService._build_movement(
            context, session, account=account,
            direction=MovementDirection.IN, amount=amount,
            movement_type=MovementType.DEPOSIT, description=description,
            reference=reference, method_id=method_id,
            movement_date=movement_date,
        )
        session.add(movement)
        session.flush()
        return movement

    @staticmethod
    @transactional
    def withdraw(context: RequestContext, session, account_id: int, amount,
                 description: str, method_id: Optional[int] = None,
                 reference: Optional[str] = None,
                 movement_date=None) -> AccountMovement:
        AccountingService._require(context, AccountingService.PERM_ACCOUNTS_MANAGE)
        account = session.get(PaymentAccount, account_id)
        if account is None:
            raise ValueError("Account not found.")

        movement = AccountingService._build_movement(
            context, session, account=account,
            direction=MovementDirection.OUT, amount=amount,
            movement_type=MovementType.WITHDRAWAL, description=description,
            reference=reference, method_id=method_id,
            movement_date=movement_date,
        )
        session.add(movement)
        session.flush()
        return movement

    @staticmethod
    @transactional
    def transfer_funds(context: RequestContext, session, from_account_id: int,
                       to_account_id: int, amount, description: Optional[str] = None,
                       reference: Optional[str] = None,
                       movement_date=None) -> List[AccountMovement]:
        AccountingService._require(context, AccountingService.PERM_ACCOUNTS_MANAGE)

        if from_account_id == to_account_id:
            raise ValueError("Choose two different accounts for a transfer.")

        source = session.get(PaymentAccount, from_account_id)
        target = session.get(PaymentAccount, to_account_id)
        if source is None or target is None:
            raise ValueError("Account not found.")
        if not source.is_active or not target.is_active:
            raise ValueError("Both accounts must be active.")

        group = str(uuid.uuid4())
        note = (description or "").strip() or (
            f"Transfer {source.name} -> {target.name}"
        )
        out_movement = AccountingService._build_movement(
            context, session, account=source,
            direction=MovementDirection.OUT, amount=amount,
            movement_type=MovementType.TRANSFER,
            description=f"Transfer to {target.name}: {note}",
            reference=reference, method_id=None,
            movement_date=movement_date, transfer_group=group,
        )
        in_movement = AccountingService._build_movement(
            context, session, account=target,
            direction=MovementDirection.IN, amount=amount,
            movement_type=MovementType.TRANSFER,
            description=f"Transfer from {source.name}: {note}",
            reference=reference, method_id=None,
            movement_date=movement_date, transfer_group=group,
        )
        session.add_all([out_movement, in_movement])
        session.flush()
        logger.info(
            f"Transferred {amount} from '{source.name}' to '{target.name}'."
        )
        return [out_movement, in_movement]

    @staticmethod
    @transactional
    def get_ledger(context: RequestContext, session, account_id: int,
                   date_from=None, date_to=None, limit: int = 500) -> dict:
        AccountingService._require(context, AccountingService.PERM_ACCOUNTS_VIEW)

        account = session.get(PaymentAccount, account_id)
        if account is None:
            raise ValueError("Account not found.")

        query = session.query(AccountMovement).filter(
            AccountMovement.account_id == account_id
        )
        if date_from is not None:
            query = query.filter(AccountMovement.movement_date >= _utc_naive(date_from))
        if date_to is not None:
            end = _utc_naive(date_to)
            query = query.filter(AccountMovement.movement_date <= end.replace(
                hour=23, minute=59, second=59
            ))
        movements = query.order_by(
            AccountMovement.movement_date, AccountMovement.id
        ).limit(int(limit)).all()

        running = Decimal(account.opening_balance or 0)
        if date_from is not None:
            prior = session.query(
                AccountMovement.direction, func.sum(AccountMovement.amount)
            ).filter(
                AccountMovement.account_id == account_id,
                AccountMovement.movement_date < _utc_naive(date_from),
            ).group_by(AccountMovement.direction).all()
            for direction, total in prior:
                signed = Decimal(total or 0)
                running += signed if direction == MovementDirection.IN else -signed

        rows = []
        for movement in movements:
            signed = movement.amount
            if movement.direction == MovementDirection.OUT:
                signed = -signed
            running += signed
            rows.append({
                "id": movement.id,
                "date": movement.movement_date,
                "type": movement.movement_type,
                "direction": movement.direction,
                "reference": movement.reference or "",
                "description": movement.description,
                "amount": movement.amount,
                "balance": running,
            })

        return {
            "account": {
                "id": account.id,
                "name": account.name,
                "account_number": account.account_number or "",
                "bank": account.bank or "",
                "opening_balance": Decimal(account.opening_balance or 0),
                "balance": running,
            },
            "rows": rows,
        }


# Account movements are append-only. Corrections go through a new opposite
# movement, which keeps the ledger auditable, same as AuditEvent.
@event.listens_for(AccountMovement, "before_update")
def _reject_movement_update(mapper, connection, target):
    raise ValueError("Account movements are immutable: record a correcting movement.")


@event.listens_for(AccountMovement, "before_delete")
def _reject_movement_delete(mapper, connection, target):
    raise ValueError("Account movements are immutable: they cannot be deleted.")
