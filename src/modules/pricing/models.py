"""Pricing engine models.

Stores discount policies that adjust a product's base price at the moment
of sale: volume tiers (buy 10, get 10% off) and customer-specific
negotiated pricing. A policy with customer_id = NULL is a global policy
that applies to every customer.
"""
from enum import Enum
from typing import Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, Numeric, Integer, DateTime, Enum as SQLAlchemyEnum, Index

from src.database.base import BaseModel
from src.modules.sales.models import SaleChannel


class PolicyScope(str, Enum):
    """Whether a policy targets one customer or every customer."""
    GLOBAL = "Global"
    CUSTOMER = "Customer"


class PricingPolicy(BaseModel):
    """
    A discount rule applied on top of a product's base price.

    Resolution order implemented by PricingService.get_effective_price:
      1. Customer-specific policies beat global ones.
      2. Higher `priority` wins among equally specific policies.
      3. The largest applicable `discount_percent` wins.
    """
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    # NULL = global policy applying to all customers.
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customer.id"), nullable=True, index=True)

    # Discount only applies from this quantity onwards (volume tiering).
    min_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)

    # Channel-specific pricing. Website and store may have different deals.
    channel: Mapped[SaleChannel] = mapped_column(SQLAlchemyEnum(SaleChannel), default=SaleChannel.STORE, nullable=False)

    # Validity window. valid_until = NULL means "no expiry".
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Tie-breaker when several policies are otherwise equally applicable.
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships are declared as plain FKs (no ORM relationship object) to
    # avoid cross-domain import cycles, matching the existing pattern used by
    # Product.supplier_id and Invoice.customer_id.

    __table_args__ = (
        # The pricing query filters on product + quantity + validity window.
        Index("ix_pricing_policy_lookup", "product_id", "min_quantity"),
    )

    @property
    def scope(self) -> PolicyScope:
        """Whether this policy is global or customer-specific."""
        return PolicyScope.CUSTOMER if self.customer_id is not None else PolicyScope.GLOBAL
