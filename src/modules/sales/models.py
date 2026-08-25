from enum import Enum
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Numeric, Integer, Date, DateTime, Enum as SQLAlchemyEnum

from src.database.base import BaseModel

class InvoiceState(str, Enum):
    """Lifecycle states for an Invoice."""
    DRAFT = "Draft"
    VALIDATED = "Validated"
    ISSUED = "Issued"
    PAID = "Paid"
    ARCHIVED = "Archived"

class QuotationState(str, Enum):
    """Lifecycle states for a Quotation."""
    DRAFT = "Draft"
    SENT = "Sent"
    ACCEPTED = "Accepted"
    CONVERTED = "Converted"
    ARCHIVED = "Archived"

class Invoice(BaseModel):
    """
    Represents a legal financial document (Invoice).
    """
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    state: Mapped[InvoiceState] = mapped_column(SQLAlchemyEnum(InvoiceState), default=InvoiceState.DRAFT, nullable=False)
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    
    # Payment terms (facture à terme): when payment is expected. Null = immediate.
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    customer: Mapped["Customer"] = relationship("Customer") # type: ignore
    items: Mapped[List["InvoiceItem"]] = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

class InvoiceItem(BaseModel):
    """
    Line item for an Invoice.
    """
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    
    # Actual cost captured at sale time -> exact margin analysis (never recomputed later)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    
    # Optional free-text override shown on the printed facture (e.g. installation details)
    description_override: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Warranty tracking (default 1 year; motors may use up to 120 months)
    warranty_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    warranty_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")
    product: Mapped["Product"] = relationship("Product") # type: ignore


class PaymentMethod(str, Enum):
    """How money moves. Morocco: cash, checks, bank transfers (virements)."""
    CASH = "Cash"
    CHECK = "Check"
    TRANSFER = "Bank Transfer"


class Payment(BaseModel):
    """
    Money actually received against an Invoice.
    An invoice may have several partial payments (cash + check + transfer).
    """
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), nullable=False, index=True)
    method: Mapped[PaymentMethod] = mapped_column(SQLAlchemyEnum(PaymentMethod), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # For CHECK payments: link to the Check ledger entry in Finance.
    check_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checks.id"), nullable=True)
    # For TRANSFER payments: bank reference. For CHECK: the check number.
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    invoice: Mapped["Invoice"] = relationship("Invoice") # type: ignore


class DepositState(str, Enum):
    """Lifecycle of a customer deposit ('bon')."""
    OPEN = "Open"          # Money held, not fully consumed
    SETTLED = "Settled"    # Fully consumed by invoices
    CANCELLED = "Cancelled"


class CustomerDeposit(BaseModel):
    """
    Advance payment from a customer ('bon'): customer pays now, receives
    goods later. Amount_used tracks how much has been applied to invoices.
    """
    deposit_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_used: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    state: Mapped[DepositState] = mapped_column(SQLAlchemyEnum(DepositState), default=DepositState.OPEN, nullable=False)
    
    method: Mapped[PaymentMethod] = mapped_column(SQLAlchemyEnum(PaymentMethod), default=PaymentMethod.CASH, nullable=False)
    check_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checks.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    customer: Mapped["Customer"] = relationship("Customer") # type: ignore


class ReturnType(str, Enum):
    """Customer returns money back OR swaps for another product."""
    REFUND = "Refund"
    EXCHANGE = "Exchange"


class ReturnState(str, Enum):
    DRAFT = "Draft"
    VALIDATED = "Validated"
    ARCHIVED = "Archived"


class SalesReturn(BaseModel):
    """
    A customer return against a validated invoice.
    Refund: money goes back to the customer. Exchange: replacement goods given.
    Defective units may be sent back to the factory (tracked per item).
    """
    return_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoice.id"), nullable=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    
    return_type: Mapped[ReturnType] = mapped_column(SQLAlchemyEnum(ReturnType), nullable=False)
    state: Mapped[ReturnState] = mapped_column(SQLAlchemyEnum(ReturnState), default=ReturnState.DRAFT, nullable=False)
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice") # type: ignore
    customer: Mapped["Customer"] = relationship("Customer") # type: ignore
    items: Mapped[List["ReturnItem"]] = relationship("ReturnItem", back_populates="sales_return", cascade="all, delete-orphan")


class ReturnItem(BaseModel):
    """
    Line item of a return: what came back, how much is refunded, and where
    the unit goes (restock or sent-to-factory for repair).
    """
    return_id: Mapped[int] = mapped_column(ForeignKey("sales_return.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # refunded per unit
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Defective unit handling: restocked (sellable again) or sent to factory
    restock: Mapped[bool] = mapped_column(default=True, nullable=False)
    sent_to_factory: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    sales_return: Mapped["SalesReturn"] = relationship("SalesReturn", back_populates="items")
    product: Mapped["Product"] = relationship("Product") # type: ignore

class Quotation(BaseModel):
    """
    Represents a sales quotation.
    """
    quotation_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    state: Mapped[QuotationState] = mapped_column(SQLAlchemyEnum(QuotationState), default=QuotationState.DRAFT, nullable=False)
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    
    customer: Mapped["Customer"] = relationship("Customer") # type: ignore
    items: Mapped[List["QuotationItem"]] = relationship("QuotationItem", back_populates="quotation", cascade="all, delete-orphan")

class QuotationItem(BaseModel):
    """
    Line item for a Quotation.
    """
    quotation_id: Mapped[int] = mapped_column(ForeignKey("quotation.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    quotation: Mapped["Quotation"] = relationship("Quotation", back_populates="items")
    product: Mapped["Product"] = relationship("Product") # type: ignore
