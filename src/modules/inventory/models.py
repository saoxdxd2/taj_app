from enum import Enum
from typing import List, Optional
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
    
    # Reorder threshold: boss decides what to reorder when quantity <= min_quantity
    min_quantity: Mapped[int] = mapped_column(default=0, nullable=False)
    
    product: Mapped["Product"] = relationship("Product")


class AttributeDataType(str, Enum):
    """Dynamic attribute value types (user-definable, nothing hard-coded)."""
    TEXT = "Text"
    NUMBER = "Number"


class AttributeDef(BaseModel):
    """
    User-defined attribute definition (e.g. BTU, capacity, sound level,
    max cold temperature, energy efficiency). Created/modified/deleted by
    the user; used as filters on the website.
    """
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)   # e.g. "btu"
    label: Mapped[str] = mapped_column(String(100), nullable=False)                          # e.g. "BTU"
    data_type: Mapped[AttributeDataType] = mapped_column(SQLAlchemyEnum(AttributeDataType), default=AttributeDataType.TEXT, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)                   # e.g. "BTU", "dB", "°C"
    
    values: Mapped[List["ProductAttribute"]] = relationship("ProductAttribute", back_populates="attribute_def", cascade="all, delete-orphan")


class ProductAttribute(BaseModel):
    """
    A concrete attribute value on a product (e.g. product X has BTU=12000).
    Stored as text; NUMBER type is validated by the service layer.
    """
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    attribute_def_id: Mapped[int] = mapped_column(ForeignKey("attribute_def.id"), nullable=False, index=True)
    value_text: Mapped[str] = mapped_column(String(255), nullable=False)
    
    attribute_def: Mapped["AttributeDef"] = relationship("AttributeDef", back_populates="values")
    product: Mapped["Product"] = relationship("Product") # type: ignore

class StockMovement(BaseModel):
    """
    Immutable ledger of all stock changes.
    """
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    movement_type: Mapped[StockMovementType] = mapped_column(SQLAlchemyEnum(StockMovementType), nullable=False)
    quantity_change: Mapped[int] = mapped_column(nullable=False) # Positive or negative
    reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True) # E.g. Purchase Ref, Invoice Num
    
    product: Mapped["Product"] = relationship("Product")
