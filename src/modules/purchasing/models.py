from enum import Enum
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Numeric, Integer, Enum as SQLAlchemyEnum

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
