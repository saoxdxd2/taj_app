"""Accounting tables: payment methods, payment accounts and their ledger.

The existing sales/purchasing tables keep their historical ``PaymentMethod``
enum for compatibility. This module adds the configurable catalog and the
cash/bank accounts that the SYS7PRO-style screens manage.
"""
from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import BaseModel


class AccountType(str, Enum):
    """Kind of place where money is held."""
    CASH = "Cash"
    BANK = "Bank"


class MovementDirection(str, Enum):
    """Direction of money relative to the account."""
    IN = "In"
    OUT = "Out"


class MovementType(str, Enum):
    """Why the money moved. Used for reporting and grouping."""
    DEPOSIT = "Deposit"
    WITHDRAWAL = "Withdrawal"
    TRANSFER = "Transfer"
    SALE_PAYMENT = "Sale Payment"
    PURCHASE_PAYMENT = "Purchase Payment"
    EXPENSE = "Expense"
    ADJUSTMENT = "Adjustment"


class PaymentAccount(BaseModel):
    """A cash drawer or a bank account.

    The current balance is not stored: it is always
    ``opening_balance + sum(in) - sum(out)`` of the movements, so the
    ledger is the single source of truth and cannot drift.
    """
    __tablename__ = "payment_account"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_type: Mapped[AccountType] = mapped_column(
        SQLAlchemyEnum(AccountType), default=AccountType.CASH, nullable=False
    )
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PaymentMethodOption(BaseModel):
    """Configurable 'moyen de paiement' (cash, cheque, TPE, transfer...).

    The default accounting accounts are suggestions used to pre-select the
    account when a payment is recorded. They are not enforced, because a
    cheque can be deposited to a different bank.
    """
    __tablename__ = "payment_method_option"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    requires_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deposit_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_account.id"), nullable=True
    )
    withdrawal_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_account.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AccountMovement(BaseModel):
    """Append-only cash/bank movement.

    Corrections are recorded as an opposite movement (adjustment); the
    service never edits or deletes an existing row.
    """
    __tablename__ = "account_movement"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("payment_account.id"), nullable=False, index=True
    )
    direction: Mapped[MovementDirection] = mapped_column(
        SQLAlchemyEnum(MovementDirection), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    movement_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[MovementType] = mapped_column(
        SQLAlchemyEnum(MovementType), default=MovementType.ADJUSTMENT, nullable=False
    )

    method_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_method_option.id"), nullable=True
    )
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    # Both sides of a transfer share this value.
    transfer_group: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
