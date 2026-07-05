from enum import Enum
from typing import Optional
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Numeric, Enum as SQLAlchemyEnum

from src.database.base import BaseModel

class ProductState(str, Enum):
    """
    Lifecycle states for a Product as defined in 10_BUSINESS_ARCHITECTURE.md
    """
    DRAFT = "Draft"
    ACTIVE = "Active"
    ARCHIVED = "Archived"

class ProductType(str, Enum):
    """
    Types of products the company can sell or consume.
    """
    PHYSICAL = "Physical Product"
    CONSUMABLE = "Consumable"
    SERVICE = "Service"
    ACCESSORY = "Accessory"
    INSTALLATION_MATERIAL = "Installation Material"

class Brand(BaseModel):
    """
    Represents a product brand.
    """
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

class Category(BaseModel):
    """
    Represents a product category.
    """
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

class Product(BaseModel):
    """
    Represents a product, service, or consumable in the Inventory domain.
    """
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    product_type: Mapped[ProductType] = mapped_column(SQLAlchemyEnum(ProductType), default=ProductType.PHYSICAL, nullable=False)
    state: Mapped[ProductState] = mapped_column(SQLAlchemyEnum(ProductState), default=ProductState.DRAFT, nullable=False)
    
    # Financial fields must use Decimal for precision (No floating point money allowed)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("20.00"), nullable=False)
    
    # Relationships
    brand_id: Mapped[Optional[int]] = mapped_column(ForeignKey("brand.id"), nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("category.id"), nullable=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("supplier.id"), nullable=True)
    
    brand: Mapped[Optional["Brand"]] = relationship("Brand")
    category: Mapped[Optional["Category"]] = relationship("Category")
    # Supplier relationship would be declared here, mapped to src.modules.suppliers.models.Supplier

class StockMovementType(str, Enum):
    """Types of stock movements."""
    PURCHASE = "Purchase"
    SALE = "Sale"
    MANUAL_ADJUSTMENT = "Manual Adjustment"
    RETURN = "Return"

class StockLevel(BaseModel):
    """
    Represents the current available stock for a product.
    """
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), unique=True, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(default=0, nullable=False)
    
    product: Mapped["Product"] = relationship("Product")

class StockMovement(BaseModel):
    """
    Immutable ledger of all stock changes.
    """
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    movement_type: Mapped[StockMovementType] = mapped_column(SQLAlchemyEnum(StockMovementType), nullable=False)
    quantity_change: Mapped[int] = mapped_column(nullable=False) # Positive or negative
    reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True) # E.g. Purchase Ref, Invoice Num
    
    product: Mapped["Product"] = relationship("Product")
