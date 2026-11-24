"""Catalog snapshot: ERP -> relay.

The catalog comes from the ERP (InventoryService), never from the
website products table. Only non-archived, priced products are included,
with their base/pinned/effective prices, VAT, stock and active flag.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.core.context import RequestContext
from src.database.transaction import transactional

logger = logging.getLogger(__name__)


def build_catalog_payload(context: RequestContext, base_revision: int = 0) -> Dict[str, Any]:
    """Builds the versioned catalog payload from the current DB state.

    ``base_revision`` is the last relay revision this desktop successfully
    pushed. The relay rejects a stale base so an offline rebuild cannot
    silently overwrite a newer catalog.
    """
    from src.modules.inventory.models import (
        Product, ProductState, StockLevel, decimal_string, pinned_price_value,
    )

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
            effective = product.effective_price
            if effective <= 0:
                # Imported zero-price DRAFT stock stays out of the phone
                # catalog until a pin (or a real base price) makes it priced.
                continue
            pin = pinned_price_value(product.pinned_price)
            products.append({
                "sku": product.sku,
                "name": product.name,
                "sale_price": decimal_string(product.sale_price),
                "pinned_price": str(pin) if pin is not None else "",
                "effective_price": str(effective),
                "priced": bool(effective > 0),
                "vat_rate": str(product.vat_rate),
                "stock": int(stock.quantity) if stock else 0,
                "active": product.state == ProductState.ACTIVE,
                "category": product.category.name if product.category else None,
                "brand": product.brand.name if product.brand else None,
            })
        return products

    products = _load()  # transactional injects a managed session
    # Version is a simple content-derived counter: the relay compares it
    # to decide whether the phone needs a refresh.
    import hashlib, json
    digest = hashlib.sha256(json.dumps(products, sort_keys=True).encode()).hexdigest()
    version = int(digest[:8], 16)
    return {
        "version": version,
        "baseRevision": int(base_revision or 0),
        "products": products,
    }


def push_catalog(context: RequestContext, client, base_revision: int = 0) -> Dict[str, Any]:
    payload = build_catalog_payload(context, base_revision=base_revision)
    return client.push_catalog(
        payload["version"], payload["products"],
        base_revision=payload["baseRevision"],
    )