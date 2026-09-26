"""
Tests for the Sales DTO validation layer.

These enforce the boundary rules that used to be checked only after a
database query: positivity, monetary precision, and VAT/warranty ceilings.
"""
import pytest
from decimal import Decimal
from pydantic import ValidationError

from src.dto.sales_dto import (
    InvoiceItemCreateDTO,
    InvoiceCreateDTO,
    PaymentCreateDTO,
    PurchaseItemCreateDTO,
    two_decimal_places,
)


def _valid_item(**overrides):
    """A minimal valid invoice line, overridable per test."""
    data = dict(
        invoice_id=1,
        product_id=1,
        quantity=2,
        unit_price=Decimal("3500.00"),
        vat_rate=Decimal("20.00"),
    )
    data.update(overrides)
    return data


# --- Precision helper ---------------------------------------------------

def test_two_decimal_places_accepts_exact_amounts():
    assert two_decimal_places(Decimal("19.99")) == Decimal("19.99")
    assert two_decimal_places(Decimal("20")) == Decimal("20.00")


def test_two_decimal_places_rejects_extra_precision():
    with pytest.raises(ValueError, match="more than 2 decimal places"):
        two_decimal_places(Decimal("10.005"))


# --- InvoiceItemCreateDTO ----------------------------------------------

def test_invoice_item_dto_accepts_valid_line():
    dto = InvoiceItemCreateDTO(**_valid_item())
    assert dto.quantity == 2
    assert dto.unit_price == Decimal("3500.00")
    # Sensible defaults
    assert dto.unit_cost == Decimal("0.00")
    assert dto.warranty_months == 12
    assert dto.description_override is None


@pytest.mark.parametrize("quantity", [0, -1, 10_001])
def test_invoice_item_dto_rejects_invalid_quantity(quantity):
    with pytest.raises(ValidationError):
        InvoiceItemCreateDTO(**_valid_item(quantity=quantity))


def test_invoice_item_dto_rejects_negative_prices():
    with pytest.raises(ValidationError):
        InvoiceItemCreateDTO(**_valid_item(unit_price=Decimal("-1.00")))
    with pytest.raises(ValidationError):
        InvoiceItemCreateDTO(**_valid_item(unit_cost=Decimal("-0.01")))


def test_invoice_item_dto_rejects_vat_above_100():
    with pytest.raises(ValidationError):
        InvoiceItemCreateDTO(**_valid_item(vat_rate=Decimal("120.00")))


def test_invoice_item_dto_rejects_excess_decimal_precision():
    """Monetary columns are Numeric(_, 2); more precision is not storable."""
    with pytest.raises(ValidationError, match="more than 2 decimal places"):
        InvoiceItemCreateDTO(**_valid_item(unit_price=Decimal("3500.005")))


def test_invoice_item_dto_bounds_warranty():
    with pytest.raises(ValidationError):
        InvoiceItemCreateDTO(**_valid_item(warranty_months=121))
    with pytest.raises(ValidationError):
        InvoiceItemCreateDTO(**_valid_item(warranty_months=-1))
    assert InvoiceItemCreateDTO(**_valid_item(warranty_months=120)).warranty_months == 120


def test_invoice_item_dto_rejects_non_positive_ids():
    with pytest.raises(ValidationError):
        InvoiceItemCreateDTO(**_valid_item(invoice_id=0))
    with pytest.raises(ValidationError):
        InvoiceItemCreateDTO(**_valid_item(product_id=0))


def test_invoice_item_dto_forbids_unknown_fields():
    """A typo must fail loudly rather than be silently dropped."""
    with pytest.raises(ValidationError):
        InvoiceItemCreateDTO(**_valid_item(quantitty=3))


# --- Other DTOs ---------------------------------------------------------

def test_invoice_create_dto_allows_anonymous_cash_sale():
    """customer_id=None is legitimate: a walk-in cash sale."""
    dto = InvoiceCreateDTO()
    assert dto.customer_id is None
    assert dto.channel == "store"


def test_payment_dto_requires_strictly_positive_amount():
    with pytest.raises(ValidationError):
        PaymentCreateDTO(invoice_id=1, method="Cash", amount=Decimal("0.00"))
    with pytest.raises(ValidationError):
        PaymentCreateDTO(invoice_id=1, method="Cash", amount=Decimal("-5.00"))


def test_purchase_item_dto_validates_cost():
    with pytest.raises(ValidationError):
        PurchaseItemCreateDTO(purchase_id=1, product_id=1, quantity=1, unit_cost=Decimal("-1.00"))
    with pytest.raises(ValidationError, match="more than 2 decimal places"):
        PurchaseItemCreateDTO(purchase_id=1, product_id=1, quantity=1, unit_cost=Decimal("99.999"))
