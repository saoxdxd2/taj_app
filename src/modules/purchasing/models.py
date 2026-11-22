from enum import Enum
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (String, ForeignKey, Numeric, Integer, Text, Boolean,
                        Date, DateTime, UniqueConstraint, Enum as SQLAlchemyEnum)

from src.database.base import BaseModel

class PurchaseState(str, Enum):
    """
    Lifecycle states for a Purchase.
    """
    DRAFT = "Draft"
    VALIDATED = "Validated"

class Purchase(BaseModel):
    """
    Represents a purchase from a supplier.
    """
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier.id"), nullable=False, index=True)
    state: Mapped[PurchaseState] = mapped_column(SQLAlchemyEnum(PurchaseState), default=PurchaseState.DRAFT, nullable=False)
    
    # Financial summary
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    # Paper trail when the purchase comes from a scanned supplier invoice
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    supplier_invoice_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    source_file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("supplier_id", "supplier_invoice_no", name="uq_purchase_supplier_invoice"),
    )
    
    # Relationships
    supplier: Mapped["Supplier"] = relationship("Supplier") # type: ignore
    items: Mapped[List["PurchaseItem"]] = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")

class PurchaseItem(BaseModel):
    """
    Represents a single line item within a Purchase.
    """
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchase.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Relationships
    purchase: Mapped["Purchase"] = relationship("Purchase", back_populates="items")
    product: Mapped["Product"] = relationship("Product") # type: ignore


class SupplierInvoiceProfile(BaseModel):
    """
    A confirmed reading of one supplier's invoice layout.

    ``fingerprint`` identifies the table header of that layout and
    ``rules_json`` stores the column ranges (as page-width fractions) that
    were reviewed and accepted, so later scans of the same layout are read
    without asking the user again.
    """
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("supplier.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    rules_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("supplier_id", "fingerprint", name="uq_supplier_invoice_profile"),
    )
