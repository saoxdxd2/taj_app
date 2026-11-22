"""Turn a scanned supplier invoice into a Draft purchase.

The flow is deliberately conservative: OCR + this module propose values, the
user reviews them, and only an explicit confirmation writes a Draft purchase.
Validation (stock movements, journal entries) stays a separate, deliberate
action in the Purchases screen.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from src.core.context import RequestContext
from src.database.transaction import transactional
from src.modules.audit.services import AuditService
from src.modules.inventory.services import InventoryService
from src.modules.purchasing.invoice_extraction import ExtractedInvoice, ExtractedLine, extract_invoice
from src.modules.purchasing.models import Purchase, PurchaseItem, PurchaseState, SupplierInvoiceProfile
from src.modules.purchasing.ocr import OcrUnavailable, read_page, sha256_file
from src.modules.suppliers.services import SupplierService
from src.security.permissions import PermissionManager

logger = logging.getLogger(__name__)


@dataclass
class MatchedLine:
    reference: str
    label: str
    quantity: int
    unit_cost: Decimal
    amount: Decimal
    product_id: Optional[int] = None
    product_label: str = ""
    suggestions: List[Tuple[int, str]] = field(default_factory=list)


@dataclass
class InvoiceScan:
    file_path: str
    file_hash: str
    invoice: ExtractedInvoice
    supplier_id: Optional[int] = None
    lines: List[MatchedLine] = field(default_factory=list)
    profile_id: Optional[int] = None


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", text)).strip().lower()


def _tokens(text: str) -> List[str]:
    return [token for token in _norm(text).split() if len(token) >= 2]


class InvoiceImportService:
    """OCR a supplier paper and, after review, store it as a Draft purchase."""

    @staticmethod
    def scan(context: RequestContext, file_path) -> InvoiceScan:
        PermissionManager.verify_permission(context, "Purchasing.Purchases.View")
        path = Path(file_path)
        page = read_page(path)
        profile = InvoiceImportService._profile_for_fingerprint(
            context, page_width=page.width, page_height=page.height, words=page.words
        )
        invoice = extract_invoice(page.width, page.height, page.words, profile=profile)
        file_hash = sha256_file(path)

        scan = InvoiceScan(file_path=str(path), file_hash=file_hash, invoice=invoice)
        if profile:
            scan.profile_id = profile.get("id")
        scan.supplier_id = InvoiceImportService._detect_supplier(context, invoice)
        scan.lines = InvoiceImportService._match_products(context, invoice.lines, scan.supplier_id)
        return scan

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    @staticmethod
    def _profile_for_fingerprint(context: RequestContext, page_width: float,
                                 page_height: float, words) -> Optional[dict]:
        """Read the layout once to learn its fingerprint, then load a saved profile."""
        dry_run = extract_invoice(page_width, page_height, words)
        if not dry_run.fingerprint:
            return None
        profile_id = None
        saved_columns = None
        try:
            from src.database.session import SessionLocal
            with SessionLocal() as session:
                row = (
                    session.query(SupplierInvoiceProfile)
                    .filter(
                        SupplierInvoiceProfile.fingerprint == dry_run.fingerprint,
                        SupplierInvoiceProfile.is_active.is_(True),
                    )
                    .order_by(SupplierInvoiceProfile.last_used_at.desc().nullslast())
                    .first()
                )
                if row is not None:
                    profile_id = row.id
                    saved_columns = json.loads(row.rules_json)
        except Exception:  # noqa: BLE001 - a missing profile must never block a scan
            logger.exception("Could not load supplier invoice profiles")
        if not saved_columns:
            return None
        merged = dict(saved_columns)
        if "columns" not in merged:
            merged = {"columns": saved_columns}
        merged["id"] = profile_id
        return merged

    @staticmethod
    def _detect_supplier(context: RequestContext, invoice: ExtractedInvoice) -> Optional[int]:
        entities = SupplierService.get_all_suppliers(context, limit=500)
        active = [supplier for supplier in entities if not supplier.is_archived]
        if not active:
            return None

        text = _norm(invoice.text)
        ice = re.sub(r"\D", "", invoice.supplier_ice or "")
        best: Optional[Tuple[int, str]] = None
        best_score = 0
        for supplier in active:
            score = 0
            supplier_ice = re.sub(r"\D", "", supplier.ice_number or "")
            if ice and supplier_ice and ice == supplier_ice:
                score += 1000
            name_tokens = [token for token in _tokens(supplier.company_name) if len(token) >= 3]
            if name_tokens:
                hits = sum(1 for token in name_tokens if token in text)
                if hits == len(name_tokens):
                    score += 45 + 10 * hits
                elif hits >= 2:
                    score += 10 * hits
            if score > best_score:
                best, best_score = (supplier.id, supplier.company_name), score
        if best is None or best_score < 40:
            return None
        return best[0]

    @staticmethod
    def _match_products(context: RequestContext, lines: Sequence[ExtractedLine],
                        supplier_id: Optional[int]) -> List[MatchedLine]:
        products = InventoryService.get_all_products(context, limit=2000)
        active = [product for product in products if product.state.value != "Archived"]
        matched: List[MatchedLine] = []
        for line in lines:
            scored: List[Tuple[float, int, str]] = []
            line_tokens = set(_tokens(line.reference + " " + line.label))
            for product in active:
                score = 0.0
                sku = _norm(product.sku)
                if sku and sku == _norm(line.reference):
                    score = 100.0
                elif sku and (sku in _norm(line.reference) or _norm(line.reference) in sku):
                    score = 75.0
                else:
                    name_tokens = set(_tokens(product.name))
                    if name_tokens and line_tokens:
                        overlap = len(name_tokens & line_tokens)
                        score = 60.0 * overlap / max(len(name_tokens), 1)
                        if supplier_id and product.supplier_id == supplier_id:
                            score += 5.0
                if score > 0:
                    scored.append((score, product.id, f"[{product.sku}] {product.name}"))
            scored.sort(key=lambda item: item[0], reverse=True)
            best = scored[0] if scored and scored[0][0] >= 45 else None
            matched.append(MatchedLine(
                reference=line.reference,
                label=line.label,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                amount=line.amount,
                product_id=best[1] if best else None,
                product_label=best[2] if best else "",
                suggestions=[(item[1], item[2]) for item in scored[:5]],
            ))
        return matched

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def save_scan(context: RequestContext, session, *, file_path: str, file_hash: str,
                  fingerprint: str, supplier_id: int, reference: str,
                  invoice_no: Optional[str], invoice_date: Optional[date],
                  items: Sequence[dict], columns: Optional[dict] = None,
                  remember_format: bool = True) -> Purchase:
        PermissionManager.verify_permission(context, "Purchasing.Purchases.Create")

        supplier = SupplierService.get_all_suppliers(context, session=session, limit=2000)
        supplier_row = next((row for row in supplier if row.id == supplier_id), None)
        if supplier_row is None:
            raise ValueError("Select a supplier for this purchase.")
        if supplier_row.is_archived:
            raise ValueError("That supplier is archived.")

        if not items:
            raise ValueError("An invoice must have at least one line.")

        supplier_invoice_no = (invoice_no or "").strip() or None
        if supplier_invoice_no:
            duplicate = (
                session.query(Purchase)
                .filter(
                    Purchase.supplier_id == supplier_id,
                    Purchase.supplier_invoice_no == supplier_invoice_no,
                )
                .first()
            )
            if duplicate is not None:
                raise ValueError(
                    f"Invoice {supplier_invoice_no} was already imported as {duplicate.reference}."
                )
        duplicate_file = (
            session.query(Purchase)
            .filter(Purchase.source_file_hash == file_hash)
            .first()
        )
        if duplicate_file is not None:
            raise ValueError(
                f"This exact scan was already imported as {duplicate_file.reference}."
            )

        purchase = Purchase(
            reference=InvoiceImportService._unique_reference(session, reference, supplier_invoice_no),
            supplier_id=supplier_id,
            state=PurchaseState.DRAFT,
            total_amount=Decimal("0.00"),
            purchase_date=invoice_date,
            supplier_invoice_no=supplier_invoice_no,
            source_file_hash=file_hash,
            source_file_name=Path(file_path).name,
        )
        session.add(purchase)
        session.flush()

        total = Decimal("0.00")
        for item in items:
            product_id = item.get("product_id")
            quantity = int(item.get("quantity") or 0)
            unit_cost = Decimal(str(item.get("unit_cost") or "0"))
            if not product_id:
                raise ValueError(
                    f"Line '{item.get('label') or item.get('reference')}' has no product. "
                    "Map every line to an inventory product before saving."
                )
            if quantity <= 0:
                raise ValueError("Every line needs a quantity greater than zero.")
            if unit_cost < 0:
                raise ValueError("Unit cost cannot be negative.")
            session.add(PurchaseItem(
                purchase_id=purchase.id,
                product_id=product_id,
                quantity=quantity,
                unit_cost=unit_cost,
            ))
            total += Decimal(quantity) * unit_cost
        purchase.total_amount = total
        session.flush()

        if remember_format and fingerprint and columns:
            InvoiceImportService._remember_layout(
                session, supplier_id, supplier_row.company_name, fingerprint, columns
            )

        AuditService.record_event(
            session=session,
            action="IMPORT_SUPPLIER_INVOICE",
            entity_name="Purchase",
            entity_id=str(purchase.id),
            after_values={
                "reference": purchase.reference,
                "supplier_invoice_no": supplier_invoice_no,
                "total_amount": float(purchase.total_amount),
                "items_count": len(items),
                "source_file": purchase.source_file_name,
            },
            user_id=context.user_id,
            correlation_id=file_hash[:16],
        )
        logger.info("Imported scanned invoice %s as draft %s", supplier_invoice_no, purchase.reference)
        return purchase

    @staticmethod
    def _unique_reference(session, reference: str, invoice_no: Optional[str]) -> str:
        base = (reference or "").strip() or (invoice_no or "")
        if not base:
            base = "SCAN-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        candidate = base[:50]
        suffix = 2
        while session.query(Purchase).filter(Purchase.reference == candidate).first() is not None:
            tail = f"-{suffix}"
            candidate = base[: 50 - len(tail)] + tail
            suffix += 1
        return candidate

    @staticmethod
    def _remember_layout(session, supplier_id: int, supplier_name: str,
                         fingerprint: str, columns: dict) -> None:
        rules = json.dumps({"columns": columns}, ensure_ascii=True)
        profile = (
            session.query(SupplierInvoiceProfile)
            .filter(
                SupplierInvoiceProfile.supplier_id == supplier_id,
                SupplierInvoiceProfile.fingerprint == fingerprint,
            )
            .first()
        )
        now = datetime.now(timezone.utc)
        if profile is None:
            session.add(SupplierInvoiceProfile(
                supplier_id=supplier_id,
                name=supplier_name,
                fingerprint=fingerprint,
                rules_json=rules,
                is_active=True,
                last_used_at=now,
            ))
        else:
            profile.rules_json = rules
            profile.is_active = True
            profile.last_used_at = now
        session.flush()
