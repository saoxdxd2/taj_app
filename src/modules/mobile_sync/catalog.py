"""Catalog snapshot: ERP -> relay.

The catalog comes from the ERP (InventoryService), never from the
website products table. Only non-archived products are included, with
their store price, VAT, stock quantity and active flag.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.core.context import RequestContext
from src.database.transaction import transactional

logger = logging.getLogger(__name__)


def build_catalog_payload(context: RequestContext) -> Dict[str, Any]:
    """Builds the versioned catalog payload from the current DB state."""
    from src.modules.inventory.models import Product, ProductState, StockLevel

    @transactional
    def _load(session):
        rows = (
            session.query(Product, StockLevel)
            .outerjoin(StockLevel, StockLevel.product_id == Product.id)
            .filter(Product.state != ProductState.ARCHIVED)
            .all()
        )
        products: List[Dict[str, Any]] = []
        for product, stock in rows:
            products.append({
                "sku": product.sku,
                "name": product.name,
                "sale_price": str(product.sale_price),
                "vat_rate": str(product.vat_rate),
                "stock": int(stock.quantity) if stock else 0,
                "active": product.state == ProductState.ACTIVE,
                "category": product.category.name if product.category else None,
                "brand": product.brand.name if product.brand else None,
            })
        return products

    products = _load(context)
    # Version is a simple content-derived counter: the relay compares it
    # to decide whether the phone needs a refresh.
    import hashlib, json
    digest = hashlib.sha256(json.dumps(products, sort_keys=True).encode()).hexdigest()
    version = int(digest[:8], 16)
    return {"version": version, "products": products}


def push_catalog(context: RequestContext, client) -> Dict[str, Any]:
    payload = build_catalog_payload(context)
    return client.push_catalog(payload["version"], payload["products"])