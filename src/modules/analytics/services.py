import logging
import math
from datetime import datetime, timedelta, timezone
from typing import List

from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.database.transaction import transactional

logger = logging.getLogger(__name__)


class ForecastService:
    """
    Simple, explainable demand forecasting for reordering:
    average sales velocity over a lookback window drives the suggested
    reorder quantity for the coming horizon. No black boxes — the boss
    can verify every number.
    """

    @staticmethod
    @transactional
    def get_reorder_suggestions(context: RequestContext, session,
                                lookback_days: int = 90,
                                horizon_days: int = 30) -> List[dict]:
        """
        Suggests how much of each product to buy to cover the next
        `horizon_days`, based on actual sales over the last `lookback_days`.

        Returns products sorted by urgency (largest shortfall first):
        {sku, name, stock, min_quantity, sold_in_window, daily_velocity,
         horizon_need, suggested_qty}
        """
        PermissionManager.verify_permission(context, "Inventory.Products.View")
        session.flush()

        if lookback_days <= 0 or horizon_days <= 0:
            raise ValueError("lookback_days and horizon_days must be positive.")

        from sqlalchemy import func
        from src.modules.inventory.models import Product, ProductState, StockLevel
        from src.modules.sales.models import Invoice, InvoiceItem, InvoiceState

        window_start = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        sold_rows = (
            session.query(
                InvoiceItem.product_id,
                func.coalesce(func.sum(InvoiceItem.quantity), 0),
            )
            .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
            .filter(
                Invoice.state.in_([InvoiceState.VALIDATED, InvoiceState.ISSUED, InvoiceState.PAID]),
                Invoice.created_at >= window_start,
            )
            .group_by(InvoiceItem.product_id)
            .all()
        )
        sold_by_product = {pid: int(total or 0) for pid, total in sold_rows}

        rows = (
            session.query(Product, StockLevel)
            .outerjoin(StockLevel, StockLevel.product_id == Product.id)
            .filter(Product.state == ProductState.ACTIVE)
            .all()
        )

        suggestions = []
        for product, stock in rows:
            qty = int(stock.quantity) if stock else 0
            threshold = int(stock.min_quantity) if stock and stock.min_quantity else 0

            # Only products the boss actually tracks for reordering
            if threshold <= 0:
                continue

            sold = sold_by_product.get(product.id, 0)
            daily_velocity = sold / float(lookback_days)
            horizon_need = math.ceil(daily_velocity * horizon_days)
            suggested = max(0, max(horizon_need - qty, threshold - qty))

            if suggested > 0:
                suggestions.append({
                    "sku": product.sku,
                    "name": product.name,
                    "stock": qty,
                    "min_quantity": threshold,
                    "sold_in_window": sold,
                    "daily_velocity": round(daily_velocity, 3),
                    "horizon_need": horizon_need,
                    "suggested_qty": suggested,
                })

        suggestions.sort(key=lambda s: s["suggested_qty"], reverse=True)
        logger.info(f"Reorder forecast: {len(suggestions)} product(s) need restocking "
                    f"(window={lookback_days}d, horizon={horizon_days}d).")
        return suggestions