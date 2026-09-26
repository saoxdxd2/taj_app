"""Pydantic DTOs for the Sales and Purchasing domains.

These objects exist to validate input at the boundary of the business
layer, before any database query runs. They encode the invariants that
would otherwise be checked only after a row has already been read.

Money is always Decimal. Floating-point money is forbidden by
11_DATABASE_STANDARD.md, and monetary columns are Numeric(12, 2), so
quantities are restricted to two decimal places.
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Reused to enforce the Numeric(_, 2) precision of every monetary column.
TWO_DP_QUANTUM = Decimal("0.01")

# Business ceilings. A single invoice line may not exceed this quantity
# (guards against a mistyped keypress faking 10 million units).
MAX_LINE_QUANTITY = 10_000

# Warranty is 0-120 months (0 = none, up to 10 years for motors).
MAX_WARRANTY_MONTHS = 120

# VAT is a percentage: 0 (exempt) to 100.
MAX_VAT_RATE = Decimal("100")


def two_decimal_places(value: Decimal) -> Decimal:
    """Validates and quantizes a monetary amount to two decimal places.

    Raises:
        ValueError: If the value has more than 2 decimal places.
    """
    quantized = value.quantize(TWO_DP_QUANTUM)
    if quantized != value:
        raise ValueError(
            f"{value} has more than 2 decimal places; maximum precision is 2."
        )
    return quantized


class DTOBase(BaseModel):
    """Common configuration for all DTOs.

    `extra="forbid"` makes a typo in a field name a loud validation
    error instead of a silently ignored value.
    """

    model_config = ConfigDict(extra="forbid")


class InvoiceItemCreateDTO(DTOBase):
    """A single line to add to a draft invoice.

    Validates the same rules the service previously checked after
    loading the invoice, but now before any database access.
    """

    invoice_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=MAX_LINE_QUANTITY)
    unit_price: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(ge=0, le=MAX_VAT_RATE)
    unit_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    description_override: Optional[str] = Field(default=None, max_length=255)
    warranty_months: int = Field(default=12, ge=0, le=MAX_WARRANTY_MONTHS)

    @field_validator("unit_price", "vat_rate", "unit_cost")
    @classmethod
    def validate_decimal_precision(cls, value: Decimal) -> Decimal:
        """Enforces the 2-decimal precision of the underlying columns."""
        return two_decimal_places(value)


class InvoiceCreateDTO(DTOBase):
    """Creation payload for an invoice draft.

    `customer_id=None` means an anonymous cash sale, which the service
    books on the shared walk-in customer.
    """

    customer_id: Optional[int] = None
    invoice_number: Optional[str] = Field(default=None, max_length=50)
    channel: str = "store"
    due_date: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreateDTO(DTOBase):
    """A payment recorded against a validated invoice."""

    invoice_id: int = Field(gt=0)
    method: str
    amount: Decimal = Field(gt=0)
    check_id: Optional[int] = Field(default=None, gt=0)
    reference: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_decimal_precision(cls, value: Decimal) -> Decimal:
        """Enforces the 2-decimal precision of the underlying column."""
        return two_decimal_places(value)


class PurchaseItemCreateDTO(DTOBase):
    """A single line to add to a purchase order draft."""

    purchase_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=MAX_LINE_QUANTITY)
    unit_cost: Decimal = Field(ge=0)

    @field_validator("unit_cost")
    @classmethod
    def validate_decimal_precision(cls, value: Decimal) -> Decimal:
        """Enforces the 2-decimal precision of the underlying column."""
        return two_decimal_places(value)
