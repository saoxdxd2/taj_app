"""Imported bank statements and the reconciliation state of each line.

The journal (``AccountMovement``) records what the app *thinks* happened. A
bank statement records what the bank *says* happened. Reconciliation links
the two without rewriting either: imported lines live in their own tables,
and a match points at the invoice, purchase or payment it explains.
"""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import BaseModel


class StatementStatus(str, Enum):
    OPEN = "Open"
    RECONCILED = "Reconciled"


class TransactionStatus(str, Enum):
    PENDING = "Pending"
    MATCHED = "Matched"
    IGNORED = "Ignored"


class TransactionCategory(str, Enum):
    UNCLASSIFIED = "Unclassified"
    CUSTOMER_RECEIPT = "Customer Receipt"
    CUSTOMER_CHEQUE_BATCH = "Customer Cheque Batch"
    SUPPLIER_PAYMENT = "Supplier Payment"
    CHEQUE_ISSUED = "Cheque Issued"
    BANK_FEE = "Bank Fee"
    TAX = "Tax"
    INTERNAL_TRANSFER = "Internal Transfer"
    OTHER = "Other"


class MatchMethod(str, Enum):
    MANUAL = "Manual"
    SUGGESTED = "Suggested"
    RULE = "Rule"


class RuleDirection(str, Enum):
    ANY = "Any"
    IN = "In"
    OUT = "Out"


class BankStatement(BaseModel):
    """One imported file for one payment account and period."""
    __tablename__ = "bank_statement"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("payment_account.id"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 of the file bytes: re-importing the same download is refused.
    file_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    bank_profile: Mapped[str] = mapped_column(String(50), nullable=False)
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    opening_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    closing_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    # Totals printed by the bank; used to verify the parse before saving.
    declared_debit_total: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    declared_credit_total: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    status: Mapped[StatementStatus] = mapped_column(
        SQLAlchemyEnum(StatementStatus), default=StatementStatus.OPEN, nullable=False
    )
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    imported_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    transactions: Mapped[List["BankTransaction"]] = relationship(
        "BankTransaction", back_populates="statement",
        cascade="all, delete-orphan", order_by="BankTransaction.line_no",
    )


class BankTransaction(BaseModel):
    """A single line of the statement, exactly as imported."""
    __tablename__ = "bank_transaction"

    statement_id: Mapped[int] = mapped_column(
        ForeignKey("bank_statement.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)

    operation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    # Wrapped continuation lines, kept verbatim for evidence and RIBs.
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    debit: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    counterparty: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    counterparty_rib: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Cheque number, batch reference or transfer reference read from the line.
    reference: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    category: Mapped[TransactionCategory] = mapped_column(
        SQLAlchemyEnum(TransactionCategory),
        default=TransactionCategory.UNCLASSIFIED, nullable=False,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        SQLAlchemyEnum(TransactionStatus),
        default=TransactionStatus.PENDING, nullable=False, index=True,
    )
    match_method: Mapped[Optional[MatchMethod]] = mapped_column(
        SQLAlchemyEnum(MatchMethod), nullable=True
    )
    match_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    statement: Mapped["BankStatement"] = relationship(
        "BankStatement", back_populates="transactions"
    )
    allocations: Mapped[List["BankAllocation"]] = relationship(
        "BankAllocation", back_populates="transaction",
        cascade="all, delete-orphan",
    )


class BankAllocation(BaseModel):
    """How much of one statement line settles a document.

    A single credit can settle several invoices (a batch of cheques), and a
    single invoice can be settled by several lines (instalments).
    """
    __tablename__ = "bank_allocation"

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("bank_transaction.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoice.id"), nullable=True, index=True
    )
    purchase_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("purchase.id"), nullable=True, index=True
    )
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment.id"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    transaction: Mapped["BankTransaction"] = relationship(
        "BankTransaction", back_populates="allocations"
    )


class BankRule(BaseModel):
    """A user rule applied to statement labels on import."""
    __tablename__ = "bank_rule"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    direction: Mapped[RuleDirection] = mapped_column(
        SQLAlchemyEnum(RuleDirection), default=RuleDirection.ANY, nullable=False
    )
    category: Mapped[TransactionCategory] = mapped_column(
        SQLAlchemyEnum(TransactionCategory), nullable=False
    )
    counterparty: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BankCounterparty(BaseModel):
    """Remembers a beneficiary RIB so the next statement identifies it."""
    __tablename__ = "bank_counterparty"
    __table_args__ = (
        UniqueConstraint("account_id", "rib", name="uq_bank_counterparty_rib"),
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("payment_account.id"), nullable=False, index=True
    )
    rib: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customer.id"), nullable=True
    )
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("supplier.id"), nullable=True
    )
