from enum import Enum
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Numeric, Integer, Enum as SQLAlchemyEnum

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
    
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")
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
