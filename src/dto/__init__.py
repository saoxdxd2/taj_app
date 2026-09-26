"""Data Transfer Object (DTO) layer.

DTOs validate user input BEFORE it reaches the service layer and the
database, so business services never have to defend against malformed
arguments (11_DATABASE_STANDARD.md: validation occurs in three layers —
UI, Business Services, Database Constraints).

DTOs are optional at the service boundary: existing callers may keep
passing primitive arguments, and the service will build the DTO for them.
"""

from src.dto.sales_dto import (
    InvoiceCreateDTO,
    InvoiceItemCreateDTO,
    PaymentCreateDTO,
    PurchaseItemCreateDTO,
    two_decimal_places,
)

__all__ = [
    "InvoiceCreateDTO",
    "InvoiceItemCreateDTO",
    "PaymentCreateDTO",
    "PurchaseItemCreateDTO",
    "two_decimal_places",
]
