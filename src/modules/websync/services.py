import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from decimal import Decimal, InvalidOperation

from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional

logger = logging.getLogger(__name__)


class WebsiteSyncService:
    """
    Keeps the boss's website in step with the ERP:
    - export_catalog: dump the sellable catalog (prices + stock) as JSON
      for upload to the website.
    - import_price_updates: apply price changes coming back from the
      website (JSON list of {sku, sale_price}).
    """

    @staticmethod
    def _build_catalog_payload(session) -> Dict:
        """Builds the catalog payload from the current session state."""
        from src.modules.inventory.models import Product, ProductState, StockLevel

        rows = (
            session.query(Product, StockLevel)
            .outerjoin(StockLevel, StockLevel.product_id == Product.id)
            .filter(Product.state != ProductState.ARCHIVED)
            .all()
        )

        products = []
        for product, stock in rows:
            products.append({
                "sku": product.sku,
                "name": product.name,
                "sale_price": float(product.sale_price or 0),
                "vat_rate": float(product.vat_rate or 0),
                "stock": int(stock.quantity) if stock else 0,
                "active": product.state == ProductState.ACTIVE,
                "category": product.category.name if product.category else None,
                "brand": product.brand.name if product.brand else None,
            })

        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "product_count": len(products),
            "products": products,
        }

    @staticmethod
    @transactional
    def export_catalog(context: RequestContext, session, output_path: str) -> Dict:
        """
        Manual export with permission check and audit trail.
        Only non-archived products are exported; stock comes from StockLevel.
        """
        PermissionManager.verify_permission(context, "Settings.WebsiteSync.Export")

        payload = WebsiteSyncService._build_catalog_payload(session)
        products = payload["products"]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        AuditService.record_event(
            session=session,
            action="EXPORT_WEBSITE_CATALOG",
            entity_name="Product",
            user_id=context.user_id,
            after_values={"path": output_path, "count": len(products)},
        )
        logger.info(f"Exported {len(products)} products to website catalog: {output_path}")
        return {"path": output_path, "count": len(products)}

    @staticmethod
    def auto_export_catalog() -> Optional[Dict]:
        """
        Silent automatic export to the sync folder using its own DB
        session. Never raises — failures are logged only. Called after
        every product/stock commit and at startup.
        """
        try:
            from src.modules.websync.sync_config import get_sync_folder
            from src.database.session import SessionLocal

            out = get_sync_folder() / "website_catalog.json"
            with SessionLocal() as session:
                payload = WebsiteSyncService._build_catalog_payload(session)
            tmp = out.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, out)  # atomic: readers never see a half file
            logger.debug(f"Auto-exported catalog ({payload['product_count']} products) to {out}")
            return {"path": str(out), "count": payload["product_count"]}
        except Exception as e:
            logger.error(f"Auto-export of website catalog failed: {e}")
            return None

    @staticmethod
    def process_pending_updates() -> Optional[Dict]:
        """
        Automatic import: looks for price_updates.json in the sync folder.
        If found, applies it and renames it to
        price_updates.applied-<timestamp>.json so it is never applied twice.
        Returns the summary dict, or None when there was nothing to do.
        Never raises — failures are logged only.
        """
        try:
            from src.modules.websync.sync_config import get_sync_folder
            from src.database.session import SessionLocal

            pending = get_sync_folder() / "price_updates.json"
            if not pending.exists():
                return None

            summary = None
            with SessionLocal() as session:
                summary = WebsiteSyncService._apply_updates(session, str(pending))
                session.commit()

            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            done = pending.with_name(f"price_updates.applied-{stamp}.json")
            os.replace(pending, done)
            logger.info(
                f"Auto-imported website prices: {summary['updated_count']} updated, "
                f"{len(summary['unknown_skus'])} unknown, {len(summary['errors'])} errors."
            )
            return summary
        except Exception as e:
            logger.error(f"Auto-import of website prices failed: {e}")
            return None

    @staticmethod
    def _apply_updates(session, input_path: str, user_id=None) -> Dict:
        """
        Core price-update application shared by the manual and automatic
        paths. Parses the JSON file and applies it to the session.
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and isinstance(data.get("products"), list):
            items = data["products"]
        else:
            raise ValueError(
                "Unsupported JSON structure: expected a list of "
                "{sku, sale_price} objects or an object with a 'products' list."
            )

        from src.modules.inventory.models import Product, ProductState

        updated, skipped_unknown, errors = [], [], []
        for i, item in enumerate(items):
            sku = str(item.get("sku", "")).strip()
            raw_price = item.get("sale_price")
            if not sku:
                errors.append(f"Entry #{i}: missing SKU.")
                continue
            try:
                price = Decimal(str(raw_price))
                if price <= 0:
                    raise InvalidOperation()
            except (InvalidOperation, TypeError, ValueError):
                errors.append(f"Entry #{i} ({sku}): invalid sale_price {raw_price!r}.")
                continue

            product = session.query(Product).filter(
                Product.sku == sku,
                Product.state != ProductState.ARCHIVED,
            ).first()
            if not product:
                skipped_unknown.append(sku)
                continue

            old_price = product.sale_price
            if old_price != price:
                product.sale_price = price
                updated.append({"sku": sku, "old_price": float(old_price or 0), "new_price": float(price)})
                AuditService.record_event(
                    session=session,
                    action="WEBSITE_PRICE_UPDATE",
                    entity_name="Product",
                    entity_id=str(product.id),
                    before_values={"sale_price": float(old_price or 0)},
                    after_values={"sale_price": float(price)},
                    user_id=user_id,
                )

        summary = {
            "updated_count": len(updated),
            "updated": updated,
            "unknown_skus": skipped_unknown,
            "errors": errors,
        }
        logger.info(
            f"Website price import: {len(updated)} updated, "
            f"{len(skipped_unknown)} unknown SKUs, {len(errors)} errors."
        )
        return summary

    @staticmethod
    @transactional
    def import_price_updates(context: RequestContext, session, input_path: str) -> Dict:
        """
        Manual import with permission check and user attribution.
        Expects a JSON file that is either a list of {sku, sale_price}
        objects or an object with a 'products' key.
        """
        PermissionManager.verify_permission(context, "Settings.WebsiteSync.Import")
        return WebsiteSyncService._apply_updates(session, input_path, user_id=context.user_id)
