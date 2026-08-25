from enum import Enum
from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Numeric, ForeignKey, DateTime, Enum as SQLAlchemyEnum

from src.database.base import BaseModel

class TransactionType(str, Enum):
    """
    Classifies the type of financial transaction in the journal.
    """
    SALE = "Sale"
    PURCHASE = "Purchase"
    EXPENSE = "Expense"
    PAYMENT_RECEIVED = "Payment Received"
    PAYMENT_SENT = "Payment Sent"
    MANUAL_ADJUSTMENT = "Manual Adjustment"

class FinancialJournalEntry(BaseModel):
    """
    Immutable ledger of all financial events.
    Never modify. Never delete. Only cancel/reverse.
    """
    transaction_type: Mapped[TransactionType] = mapped_column(SQLAlchemyEnum(TransactionType), nullable=False, index=True)
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True) # E.g., Invoice Number, Purchase Ref
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Positive means incoming money (Credit), Negative means outgoing money (Debit)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Link to the user who triggered the transaction (Audit requirement)
    # Using generic integer to prevent hard dependencies on auth module if separated
    user_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    is_reversed: Mapped[bool] = mapped_column(default=False, nullable=False)
    reversal_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

class ExpenseCategory(str, Enum):
    """
    Standard categories for business expenses.
    """
    SALARY = "Salary"
    UTILITIES = "Utilities"
    RENT = "Rent"
    EQUIPMENT = "Equipment"
    MARKETING = "Marketing"
    TRAVEL = "Travel"
    TAX = "Tax"
    OTHER = "Other"

class CheckDirection(str, Enum):
    """Incoming = check we must RECEIVE from a customer. Outgoing = check we must PAY."""
    INCOMING = "Incoming"
    OUTGOING = "Outgoing"


class CheckStatus(str, Enum):
    """Lifecycle of a physical check."""
    PENDING = "Pending"        # Waiting, due date in the future
    DEPOSITED = "Deposited"    # Handed to the bank
    CLEARED = "Cleared"        # Money actually moved
    BOUNCED = "Bounced"        # Unpaid (no funds)
    CANCELLED = "Cancelled"


class Check(BaseModel):
    """
    A physical check (incoming or outgoing) with its due date.
    The boss gets friendly reminders N days before each due date.
    """
    # 'check' is a SQL reserved word — use an explicit safe table name
    __tablename__ = "checks"
    
    check_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    direction: Mapped[CheckDirection] = mapped_column(SQLAlchemyEnum(CheckDirection), nullable=False, index=True)
    status: Mapped[CheckStatus] = mapped_column(SQLAlchemyEnum(CheckStatus), default=CheckStatus.PENDING, nullable=False, index=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    bank: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Denormalized display name of the payer/payee (customer or supplier)
    party_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customer.id"), nullable=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("supplier.id"), nullable=True)
    
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Expense(BaseModel):
    """
    Represents a business expense.
    Affects cash flow but not gross profit.
    """
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    category: Mapped[ExpenseCategory] = mapped_column(SQLAlchemyEnum(ExpenseCategory), default=ExpenseCategory.OTHER, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Enforces the Soft Delete Policy
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)
