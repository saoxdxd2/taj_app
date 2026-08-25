import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.database.transaction import transactional

logger = logging.getLogger(__name__)


class ReportsService:
    """
    Profit & margin analytics.

    The boss registers the REAL cost at sale time (InvoiceItem.unit_cost),
    so margins here are exact — no averages, no estimates.
    All money math uses Decimal; revenue is computed VAT-exclusive so the
    margin reflects what the business actually earns (VAT goes to the state).
    """

    @staticmethod
    @transactional
    def calculate_invoice_profit(context: RequestContext, session, invoice_id: int) -> dict:
        """
        Exact per-invoice profit from the captured unit costs:
        revenue_excl_vat - total_cost = gross_margin (+ margin %).
        """
        PermissionManager.verify_permission(context, "Reports.Profit.View")

        from src.modules.sales.models import Invoice, InvoiceState

        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice ID {invoice_id} not found.")
        if invoice.state == InvoiceState.DRAFT:
            raise ValueError("Profit is only meaningful on validated invoices.")

        revenue = Decimal("0.00")
        cost = Decimal("0.00")
        for item in invoice.items:
            revenue += Decimal(item.quantity) * item.unit_price
            cost += Decimal(item.quantity) * item.unit_cost

        margin = revenue - cost
        margin_pct = (margin / revenue * Decimal("100")) if revenue > 0 else Decimal("0.00")

        return {
            "invoice_id": invoice_id,
            "invoice_number": invoice.invoice_number,
            "revenue_excl_vat": revenue,
            "total_cost": cost,
            "gross_margin": margin,
            "margin_percent": margin_pct.quantize(Decimal("0.01")),
        }

    @staticmethod
    @transactional
    def calculate_period_profit(context: RequestContext, session,
                                start: datetime, end: datetime) -> dict:
        """
        Aggregate profit over a period (e.g. this month), computed in SQL
        (SUM of quantity*price and quantity*cost) — one query regardless of
        how many invoices/items are in range. Only validated/issued/paid
        invoices count; drafts are not real sales yet.
        """
        PermissionManager.verify_permission(context, "Reports.Profit.View")

        if start >= end:
            raise ValueError("Period start must be before end.")

        # Normalize naive datetimes to UTC-aware for comparison with
        # timezone-aware created_at columns.
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        from sqlalchemy import func
        from src.modules.sales.models import Invoice, InvoiceItem, InvoiceState

        row = (
            session.query(
                func.coalesce(func.sum(InvoiceItem.quantity * InvoiceItem.unit_price), 0),
                func.coalesce(func.sum(InvoiceItem.quantity * InvoiceItem.unit_cost), 0),
                func.count(func.distinct(Invoice.id)),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .filter(
                Invoice.state.in_([InvoiceState.VALIDATED, InvoiceState.ISSUED, InvoiceState.PAID]),
                Invoice.created_at >= start,
                Invoice.created_at < end,
            )
            .one()
        )
        revenue = Decimal(str(row[0]))
        cost = Decimal(str(row[1]))
        invoices_count = int(row[2])

        margin = revenue - cost
        margin_pct = (margin / revenue * Decimal("100")) if revenue > 0 else Decimal("0.00")

        return {
            "start": start,
            "end": end,
            "invoices_count": invoices_count,
            "revenue_excl_vat": revenue,
            "total_cost": cost,
            "gross_margin": margin,
            "margin_percent": margin_pct.quantize(Decimal("0.01")),
        }

    @staticmethod
    @transactional
    def get_top_products_by_margin(context: RequestContext, session,
                                   start: datetime, end: datetime,
                                   limit: int = 10) -> List[dict]:
        """
        Best-margin products over a period (SQL GROUP BY product).
        Helps the boss see which references actually make money.
        """
        PermissionManager.verify_permission(context, "Reports.Profit.View")

        if start >= end:
            raise ValueError("Period start must be before end.")
        if limit <= 0 or limit > 100:
            raise ValueError("Limit must be between 1 and 100.")

        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        from sqlalchemy import func
        from src.modules.sales.models import Invoice, InvoiceItem, InvoiceState
        from src.modules.inventory.models import Product

        rows = (
            session.query(
                Product.id.label("product_id"),
                Product.sku.label("sku"),
                Product.name.label("name"),
                func.sum(InvoiceItem.quantity * InvoiceItem.unit_price).label("revenue"),
                func.sum(InvoiceItem.quantity * InvoiceItem.unit_cost).label("cost"),
            )
            .join(InvoiceItem, InvoiceItem.product_id == Product.id)
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .filter(
                Invoice.state.in_([InvoiceState.VALIDATED, InvoiceState.ISSUED, InvoiceState.PAID]),
                Invoice.created_at >= start,
                Invoice.created_at < end,
            )
            .group_by(Product.id, Product.sku, Product.name)
            .order_by((func.sum(InvoiceItem.quantity * InvoiceItem.unit_price)
                       - func.sum(InvoiceItem.quantity * InvoiceItem.unit_cost)).desc())
            .limit(limit)
            .all()
        )

        result = []
        for r in rows:
            revenue = Decimal(str(r.revenue))
            cost = Decimal(str(r.cost))
            margin = revenue - cost
            result.append({
                "product_id": r.product_id,
                "sku": r.sku,
                "name": r.name,
                "revenue_excl_vat": revenue,
                "total_cost": cost,
                "gross_margin": margin,
                "margin_percent": ((margin / revenue * Decimal("100")) if revenue > 0 else Decimal("0.00")).quantize(Decimal("0.01")),
            })
        return result