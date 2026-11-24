#!/usr/bin/env python3
"""NON-DESTRUCTIVE ERP stock-import planner (and heavily guarded optional applier).

WHY THIS SCRIPT EXISTS
----------------------
150 warehouse rows / 297 units must enter the ERP, but the register has no
authoritative retail sale_price. Per docs/PINNED_PRICE_CONTRACT.md, a missing
or zero retail price is a NEEDS PRICING warning, NOT an import blocker: the
import may create a DRAFT product with sale_price=0.00, no pinned_price, and
effective_price=0 (unpriced). Unpriced products are hidden from sales surfaces
until an ERP or phone pin is entered; a pin activates the DRAFT product.
This script NEVER sets pinned_price, NEVER activates a product, and NEVER
invents, infers, or copies supplier/pro-forma prices into retail sale_price.
Unsafe numeric text, negative prices and cost/supplier price columns still
fail closed. VAT may use the ERP default 20.00 with a warning until verified.

WHAT WAS LEARNED FROM THE ERP (see stock_import/erp_field_map.json for detail)
-----------------------------------------------------------------------------
* Product required columns: name (String(255) NOT NULL, indexed), sku
  (String(50) UNIQUE NOT NULL, indexed), product_type (default Physical
  Product), state (default Draft), purchase_price (default 0.00), sale_price
  (default 0.00), sale_price_website (default 0.00), vat_rate (default 20.00),
  audit id/created_at/updated_at. InventoryService.create_product() hard-codes
  state=ProductState.DRAFT and explicitly passes the price defaults, so the
  model defaults are not a safety net. Passing None causes a TypeError in the
  service's `price < 0` checks (or a NOT NULL error on a direct insert).
* ProductState: Draft (default; visible in catalogs with active=false, not
  selectable in the phone invoice picker), Active (only via
  InventoryService.activate_product), Archived (history-preserving end of
  life, excluded from catalogs). This importer leaves products DRAFT.
* category_id / brand_id are nullable FKs. Resolution is an EXACT,
  case-sensitive name lookup on Category.name / Brand.name (both UNIQUE
  String(100) NOT NULL). The ERP has no create_category/create_brand service,
  so they normally must pre-exist; --apply get-or-creates missing ones by exact
  name inside the same transaction (additive only).
* StockLevel: one row per product (product_id UNIQUE FK NOT NULL), quantity
  default 0, min_quantity default 0. InventoryService.adjust_stock()
  get-or-creates it with quantity 0 and records an immutable StockMovement;
  that is the code path used here so stock has provenance.
* All ERP writes go through @transactional (src/database/transaction.py): one
  session, commit on success, rollback on any exception.

SAFETY CONTRACT
---------------
--dry-run (DEFAULT):
  * Never imports any src.* ERP module (importing src.core.paths would create
    TAJ_FROID directories as a side effect) and never connects read-write.
  * If the ERP DB file already exists it is probed with a READ-ONLY, IMMUTABLE
    sqlite3 URI (mode=ro&immutable=1) solely to report SKU matches; this creates
    no -wal/-shm side files. A non-empty WAL or any probe error fails closed.
  * Writes ONLY stock_import/erp_import_plan.json (a new report file).
--apply:
  * REFUSED unless BOTH --i-understand-destructive-risk is given AND
    stock_import/APPLY_APPROVED.txt contains exactly "APPROVED BY HUMAN".
    This guard runs BEFORE any ERP import or DB access.
  * Requires an already-existing ERP DB file (never creates one implicitly).
  * Idempotent get-or-create by exact SKU. Existing products are NEVER renamed,
    repriced, activated, archived or deleted. Stock is only increased to the
    manifest target; a higher existing quantity aborts the whole transaction.
  * One transaction, full rollback on any error, no DELETE statements.
  * Unpriced rows are created at sale_price=0.00 with no pin; existing products
    are never repriced, activated, archived or deleted.
  * This script was NOT executed with --apply during development/verification.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "stock_import" / "import_manifest.json"
DEFAULT_PRICES = REPO_ROOT / "stock_import" / "prices.csv"
PLAN_PATH = REPO_ROOT / "stock_import" / "erp_import_plan.json"
APPROVAL_PATH = REPO_ROOT / "stock_import" / "APPLY_APPROVED.txt"

EXPECTED_ROWS = 150
EXPECTED_UNITS = 297
APPROVAL_TEXT = "APPROVED BY HUMAN"
MONEY_QUANT = Decimal("0.01")
ERP_DEFAULT_VAT = Decimal("20.00")
UNPRICED_SALE_PRICE = Decimal("0.00")

COST_HEADER_RE = re.compile(
    r"cost|supplier|pro[\s-]?forma|purchase|wholesale|discount|tarif|fournisseur|achat",
    re.I,
)
PLACEHOLDER_PRICE_RE = re.compile(r"^(n/?a|tbd|todo|unknown|-+|\?+|pending)$", re.I)

SKU_HEADERS = ("sku", "code", "reference", "ref")
PRICE_HEADERS = ("sale_price", "price", "prix", "selling_price", "unit_price")
VAT_HEADERS = ("vat_rate", "tva", "vat")

MANIFEST_KEYS = (
    "n", "sku", "name", "qty", "status", "ledger", "category", "brand",
    "source_page", "internal_placeholder",
)


class ValidationError(Exception):
    """Raised for a fail-closed condition (kept separate from builtin ImportError)."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_of(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def erp_db_path() -> Path:
    """Mirror src/core/paths.py WITHOUT importing it (no directory side effects)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "TAJ_FROID" / "data" / "taj_froid.db"
    return Path.home() / ".taj_froid" / "data" / "taj_froid.db"


def parse_decimal(value: Any, label: str, errors: List[str], context: str,
                  *, positive: bool = False, non_negative: bool = False,
                  max_exponent: int = 2, max_abs: Decimal = Decimal("9999999999.99")) -> Optional[Decimal]:
    """Strict money parser: no floats, no hidden rounding, no infinities."""
    text = "" if value is None else str(value).strip()
    if not text:
        errors.append(f"MISSING {label} for {context}")
        return None
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        errors.append(f"INVALID {label} '{text}' for {context} (not a decimal number)")
        return None
    if not number.is_finite():
        errors.append(f"INVALID {label} '{text}' for {context} (not finite)")
        return None
    if positive and number <= 0:
        errors.append(f"ZERO_OR_NEGATIVE {label} '{text}' for {context} (must be > 0)")
        return None
    if non_negative and number < 0:
        errors.append(f"NEGATIVE {label} '{text}' for {context}")
        return None
    if number.as_tuple().exponent < -max_exponent:
        errors.append(
            f"INVALID {label} '{text}' for {context} (more than {max_exponent} decimal places; "
            "Numeric would silently round)"
        )
        return None
    if abs(number) > max_abs:
        errors.append(f"INVALID {label} '{text}' for {context} (outside Numeric column range)")
        return None
    return number


def load_manifest(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if not path.is_file():
        return [], {}, [f"Manifest not found: {path}"], warnings
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], {}, [f"Cannot read/parse manifest {path}: {exc}"], warnings

    declared_rows = data.get("rows")
    declared_units = data.get("units")
    raw_products = data.get("products")
    if not isinstance(raw_products, list):
        return [], {}, ["Manifest has no 'products' list"], warnings

    if declared_rows != EXPECTED_ROWS:
        errors.append(f"Manifest declares rows={declared_rows!r}; expected exactly {EXPECTED_ROWS}")
    if len(raw_products) != EXPECTED_ROWS:
        errors.append(f"Manifest contains {len(raw_products)} product rows; expected exactly {EXPECTED_ROWS}")
    if declared_units != EXPECTED_UNITS:
        errors.append(f"Manifest declares units={declared_units!r}; expected exactly {EXPECTED_UNITS}")

    rows: List[Dict[str, Any]] = []
    seen_skus: Dict[str, int] = {}
    seen_numbers: Set[int] = set()
    unit_sum = 0
    placeholder_count = 0

    for index, raw in enumerate(raw_products, start=1):
        where = f"manifest row #{index}"
        if not isinstance(raw, dict):
            errors.append(f"{where}: not a JSON object")
            continue
        missing = [key for key in MANIFEST_KEYS if key not in raw]
        if missing:
            errors.append(f"{where}: missing keys {missing}")
            continue

        sku = str(raw["sku"]).strip()
        name = str(raw["name"]).strip()
        category = str(raw["category"]).strip()
        brand = str(raw["brand"]).strip()
        n = raw["n"]
        qty = raw["qty"]

        if not sku:
            errors.append(f"{where}: empty SKU")
        elif sku in seen_skus:
            errors.append(
                f"DUPLICATE SKU '{sku}' at manifest rows #{seen_skus[sku]} and #{index}"
            )
        else:
            seen_skus[sku] = index
        if len(sku) > 50:
            errors.append(f"{where}: SKU length {len(sku)} exceeds Product.sku String(50)")
        if not name:
            errors.append(f"{where}: empty name")
        if len(name) > 255:
            errors.append(f"{where}: name length {len(name)} exceeds Product.name String(255)")
        if not category:
            errors.append(f"{where}: empty category")
        if len(category) > 100:
            errors.append(f"{where}: category length > Category.name String(100)")
        if not brand:
            errors.append(f"{where}: empty brand")
        if len(brand) > 100:
            errors.append(f"{where}: brand length > Brand.name String(100)")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            errors.append(f"{where}: qty must be a positive integer, got {qty!r}")
        else:
            unit_sum += qty
        if not isinstance(n, int) or isinstance(n, bool):
            errors.append(f"{where}: n must be an integer, got {n!r}")
        elif n in seen_numbers:
            errors.append(f"{where}: duplicate n={n}")
        else:
            seen_numbers.add(n)
        if not isinstance(raw["internal_placeholder"], bool):
            errors.append(f"{where}: internal_placeholder must be boolean")
        elif raw["internal_placeholder"]:
            placeholder_count += 1

        rows.append({
            "n": n,
            "sku": sku,
            "name": name,
            "qty": qty,
            "status": str(raw["status"]),
            "ledger": str(raw["ledger"]),
            "category": category,
            "brand": brand,
            "source_page": raw["source_page"],
            "internal_placeholder": bool(raw["internal_placeholder"]),
            "physical_label_check_required": bool(raw.get("physical_label_check_required", False)),
        })

    if unit_sum != EXPECTED_UNITS:
        errors.append(f"Manifest qty sum is {unit_sum}; expected exactly {EXPECTED_UNITS}")
    declared_placeholders = data.get("internal_placeholders")
    if declared_placeholders != placeholder_count:
        warnings.append(
            f"Manifest declares internal_placeholders={declared_placeholders!r} but "
            f"{placeholder_count} rows are flagged"
        )

    meta = {
        "path": str(path),
        "sha256": sha256_of(path),
        "declared_rows": declared_rows,
        "actual_rows": len(raw_products),
        "declared_units": declared_units,
        "computed_units": unit_sum,
        "declared_internal_placeholders": declared_placeholders,
        "computed_internal_placeholders": placeholder_count,
    }
    return rows, meta, errors, warnings


def load_prices(path: Path, manifest_skus: List[str], manifest_by_sku: Dict[str, Dict[str, Any]]
                ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any], List[str], List[str]]:
    """Load OPTIONAL authoritative retail prices.

    Blank/zero prices are NEEDS PRICING warnings: the row is staged at 0.00
    with no pin and DRAFT state. Invalid text, negative values and cost/
    supplier price columns remain hard errors; no supplier price is ever used.
    """
    errors: List[str] = []
    warnings: List[str] = []
    prices: Dict[str, Dict[str, Any]] = {}
    meta: Dict[str, Any] = {
        "path": str(path),
        "found": path.is_file(),
        "sha256": sha256_of(path),
        "header": None,
        "data_rows": 0,
        "missing_manifest_skus": [],
        "unpriced_skus": [],
        "priced_skus": [],
        "invalid_entries": [],
        "duplicate_csv_skus": [],
        "extra_csv_skus": [],
        "vat_fallback_count": 0,
        "note": "NEEDS PRICING rows are staged at sale_price=0.00 with pinned_price unset; no price is inferred or copied.",
    }
    if not path.is_file():
        meta["missing_manifest_skus"] = list(manifest_skus)
        meta["unpriced_skus"] = list(manifest_skus)
        warnings.append(
            f"NEEDS PRICING: no price CSV at {path}. All {len(manifest_skus)} manifest SKUs "
            "will be staged at sale_price=0.00, pinned_price unset, state DRAFT. "
            "No price is invented, inferred, or copied from supplier pro-forma data."
        )
        return prices, meta, errors, warnings

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            header = [str(h).strip().lower() if h is not None else "" for h in (reader.fieldnames or [])]
            meta["header"] = header

            def find_header(candidates: Tuple[str, ...]) -> Optional[str]:
                for wanted in candidates:
                    if wanted in header:
                        return reader.fieldnames[header.index(wanted)]
                return None

            cost_columns = [h for h in header if COST_HEADER_RE.search(h)]
            if cost_columns:
                errors.append(
                    f"Price CSV has cost/supplier/pro-forma column(s) {cost_columns}; "
                    "supplier prices must never become retail sale_price"
                )
                return prices, meta, errors, warnings
            sku_col = find_header(SKU_HEADERS)
            price_col = find_header(PRICE_HEADERS)
            vat_col = find_header(VAT_HEADERS)
            if sku_col is None:
                errors.append(f"Price CSV has no SKU column (accepted: {', '.join(SKU_HEADERS)})")
                return prices, meta, errors, warnings
            if price_col is None:
                errors.append(f"Price CSV has no sale_price column (accepted: {', '.join(PRICE_HEADERS)})")
                return prices, meta, errors, warnings

            seen_csv_skus: Dict[str, int] = {}
            for line_no, raw_row in enumerate(reader, start=2):
                if not any(str(v or "").strip() for v in raw_row.values()):
                    continue
                meta["data_rows"] += 1
                sku = str(raw_row.get(sku_col) or "").strip()
                context = f"price CSV line {line_no} (sku '{sku}')"
                if not sku:
                    errors.append(f"{context}: empty SKU")
                    continue
                if sku in seen_csv_skus:
                    errors.append(
                        f"DUPLICATE CSV SKU '{sku}' on lines {seen_csv_skus[sku]} and {line_no}"
                    )
                    meta["duplicate_csv_skus"].append(sku)
                    continue
                seen_csv_skus[sku] = line_no

                before = len(errors)
                price_text = str(raw_row.get(price_col) or "").strip()
                unpriced = not price_text or bool(PLACEHOLDER_PRICE_RE.fullmatch(price_text))
                if unpriced:
                    sale_price = UNPRICED_SALE_PRICE
                else:
                    sale_price = parse_decimal(
                        price_text, "sale_price", errors, context, non_negative=True
                    )
                    if sale_price is not None and sale_price == 0:
                        unpriced = True
                if vat_col and str(raw_row.get(vat_col) or "").strip():
                    vat_rate = parse_decimal(
                        raw_row.get(vat_col), "vat_rate", errors, context, non_negative=True,
                        max_abs=Decimal("999.99"),
                    )
                    vat_source = f"price CSV column '{vat_col}'"
                else:
                    vat_rate = ERP_DEFAULT_VAT
                    vat_source = "ERP default 20.00 (UNVERIFIED - not present in price CSV)"
                    meta["vat_fallback_count"] += 1
                    warnings.append(f"{context}: VAT absent; using UNVERIFIED ERP default 20.00")

                if len(errors) > before or sale_price is None or vat_rate is None:
                    meta["invalid_entries"].append(sku)
                    continue
                amount = str(sale_price.quantize(MONEY_QUANT))
                if unpriced:
                    meta["unpriced_skus"].append(sku)
                    warnings.append(
                        f"NEEDS PRICING for {context}: staging sale_price=0.00 with no pin; "
                        "hidden from sales until an authoritative price/pin is entered."
                    )
                else:
                    meta["priced_skus"].append(sku)
                prices[sku] = {
                    "sku": sku,
                    "sale_price": amount,
                    "effective_price": amount,
                    "pinned_price": "NOT SET (importer never pins prices)",
                    "priced": not unpriced,
                    "vat_rate": str(vat_rate.quantize(MONEY_QUANT)),
                    "vat_source": vat_source,
                    "csv_line": line_no,
                    "status": "NEEDS PRICING" if unpriced else "PRICED",
                }
    except (OSError, csv.Error, UnicodeError) as exc:
        errors.append(f"Cannot read price CSV {path}: {exc}")
        return prices, meta, errors, warnings

    missing = sorted(set(manifest_skus) - set(prices))
    meta["missing_manifest_skus"] = missing
    for sku in missing:
        row_no = manifest_by_sku[sku]["n"]
        meta["unpriced_skus"].append(sku)
        warnings.append(
            f"NEEDS PRICING for manifest row #{row_no} SKU '{sku}' (no row in {path}); "
            "staging sale_price=0.00 with no pin."
        )
    meta["unpriced_skus"] = sorted(set(meta["unpriced_skus"]))
    meta["priced_skus"] = sorted(set(meta["priced_skus"]))
    meta["extra_csv_skus"] = sorted(set(seen_csv_skus) - set(manifest_skus))
    for sku in meta["extra_csv_skus"]:
        warnings.append(f"Price CSV has extra SKU '{sku}' that is not in the manifest (ignored)")
    return prices, meta, errors, warnings


def read_existing_erp_state(db_path: Path, skus: List[str]
                            ) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
    """Optional READ-ONLY probe; returns None (fail closed) if the DB is unreadable."""
    errors: List[str] = []
    warnings: List[str] = []
    state: Dict[str, Any] = {
        "db_path": str(db_path),
        "db_exists": db_path.is_file(),
        "probe": "read-only sqlite3 URI (mode=ro&immutable=1) - no -wal/-shm side files",
        "existing_skus": {},
        "existing_categories": [],
        "existing_brands": [],
        "existing_stock": {},
    }
    if not state["db_exists"]:
        warnings.append(
            "ERP database does not exist at the expected path; all products/categories/brands "
            "will be reported as needing creation. Nothing was created by this dry-run."
        )
        return state, errors, warnings

    # A normal mode=ro connection on a WAL database creates -shm/-wal files as
    # a side effect. immutable=1 avoids that entirely. If committed data is
    # still sitting in a non-empty WAL we cannot read it without side effects,
    # so fail closed rather than reporting a stale/incorrect SKU match.
    wal_path = Path(str(db_path) + "-wal")
    if wal_path.is_file() and wal_path.stat().st_size > 0:
        errors.append(
            f"ERP database has a non-empty WAL ({wal_path}); a side-effect-free read-only "
            "probe cannot see uncheckpointed data. Failing closed; checkpoint the WAL first."
        )
        return None, errors, warnings
    uri = db_path.resolve().as_uri() + "?mode=ro&immutable=1"
    connection = None
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=5)
        connection.execute("PRAGMA query_only = ON")
        existing_sku_rows = connection.execute("SELECT sku, name FROM product").fetchall()
        state["existing_skus"] = {str(sku): str(name) for sku, name in existing_sku_rows}
        state["existing_categories"] = [str(row[0]) for row in connection.execute("SELECT name FROM category")]
        state["existing_brands"] = [str(row[0]) for row in connection.execute("SELECT name FROM brand")]
        state["existing_stock"] = {
            str(sku): int(quantity)
            for sku, quantity in connection.execute(
                "SELECT p.sku, s.quantity FROM stock_level s JOIN product p ON p.id = s.product_id"
            )
        }
        for sku in skus:
            if sku in state["existing_skus"]:
                warnings.append(
                    f"Existing product found for SKU '{sku}' (name: {state['existing_skus'][sku]}); "
                    "--apply would MATCH it, not overwrite it."
                )
    except (sqlite3.Error, OSError) as exc:
        errors.append(
            f"ERP database exists but could not be read read-only ({exc}); failing closed "
            "instead of guessing which SKUs already exist."
        )
        return None, errors, warnings
    finally:
        if connection is not None:
            connection.close()
    return state, errors, warnings


def build_plan(manifest_path: Path, prices_path: Path) -> Dict[str, Any]:
    all_errors: List[str] = []
    all_warnings: List[str] = []

    rows, manifest_meta, errors, warnings = load_manifest(manifest_path)
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    manifest_by_sku = {row["sku"]: row for row in rows}
    prices, price_meta, errors, warnings = load_prices(
        prices_path, [row["sku"] for row in rows], manifest_by_sku
    )
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    db_path = erp_db_path()
    erp_state, errors, warnings = read_existing_erp_state(db_path, [row["sku"] for row in rows])
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    if erp_state is None:
        erp_state = {
            "db_path": str(db_path), "db_exists": db_path.is_file(), "probe": "FAILED - fail closed",
            "existing_skus": {}, "existing_categories": [], "existing_brands": [], "existing_stock": {},
        }

    existing_categories = set(erp_state["existing_categories"])
    existing_brands = set(erp_state["existing_brands"])
    needed_categories = sorted({row["category"] for row in rows} - existing_categories)
    needed_brands = sorted({row["brand"] for row in rows} - existing_brands)

    planned_rows: List[Dict[str, Any]] = []
    create_skus: List[str] = []
    match_skus: List[str] = []
    for row in rows:
        sku = row["sku"]
        price = prices.get(sku)
        exists = sku in erp_state["existing_skus"]
        decision = "MATCH_BY_SKU (never overwrite)" if exists else "CREATE_PRODUCT"
        (match_skus if exists else create_skus).append(sku)

        current_stock: Optional[int] = erp_state["existing_stock"].get(sku)
        if exists:
            if current_stock is None:
                stock_action = f"CREATE StockLevel with quantity={row['qty']} via adjust_stock"
            elif current_stock > row["qty"]:
                stock_action = (
                    f"ABORT: existing stock {current_stock} > manifest qty {row['qty']} "
                    "(stock is never reduced)"
                )
                all_errors.append(f"SKU '{sku}': existing stock {current_stock} exceeds manifest qty {row['qty']}")
            elif current_stock == row["qty"]:
                stock_action = "NO CHANGE (idempotent: current stock equals manifest qty)"
            else:
                stock_action = f"INCREASE stock from {current_stock} to {row['qty']} via adjust_stock"
        else:
            stock_action = f"CREATE StockLevel with quantity={row['qty']} via adjust_stock"

        planned_rows.append({
            "n": row["n"],
            "sku": sku,
            "name": row["name"],
            "qty": row["qty"],
            "status": row["status"],
            "status_note": "QA/provenance flag only - NOT ProductState; imported products stay DRAFT",
            "ledger": row["ledger"],
            "source_page": row["source_page"],
            "internal_placeholder": row["internal_placeholder"],
            "physical_label_check_required": row["physical_label_check_required"],
            "review_required": row["internal_placeholder"] or row["status"] != "Verified",
            "category": row["category"],
            "category_action": "CREATE Category (exact name)" if row["category"] in needed_categories else "USE existing Category (exact name)",
            "brand": row["brand"],
            "brand_action": "CREATE Brand (exact name)" if row["brand"] in needed_brands else "USE existing Brand (exact name)",
            "price": price if price else {
                "sku": sku,
                "sale_price": str(UNPRICED_SALE_PRICE.quantize(MONEY_QUANT)),
                "effective_price": str(UNPRICED_SALE_PRICE.quantize(MONEY_QUANT)),
                "pinned_price": "NOT SET (importer never pins prices)",
                "priced": False,
                "vat_rate": str(ERP_DEFAULT_VAT.quantize(MONEY_QUANT)),
                "vat_source": "ERP default 20.00 (UNVERIFIED)",
                "status": "NEEDS PRICING",
                "reason": "no authoritative retail price; staged unpriced, hidden from sales until pinned",
            },
            "product_state": "Draft",
            "product_type": "Physical Product",
            "decision": decision,
            "stock_action": stock_action,
        })

    totals = {
        "manifest_rows": len(rows),
        "total_units": sum(row["qty"] for row in rows),
        "products_to_create": len(create_skus),
        "products_matched_by_sku": len(match_skus),
        "products_to_create_skus": create_skus,
        "products_matched_skus": match_skus,
        "categories_to_create": needed_categories,
        "brands_to_create": needed_brands,
        "categories_existing": sorted(existing_categories),
        "brands_existing": sorted(existing_brands),
        "internal_placeholders": sum(1 for row in rows if row["internal_placeholder"]),
        "rows_requiring_review": sum(1 for row in planned_rows if row["review_required"]),
        "prices_missing": len(price_meta["unpriced_skus"]),
        "unpriced_products": len(price_meta["unpriced_skus"]),
        "priced_products": len(price_meta["priced_skus"]),
    }

    plan: Dict[str, Any] = {
        "report_type": "erp_import_plan",
        "mode": "dry-run",
        "generated_at_utc": now_utc(),
        "purpose": "Pre import verification only. No ERP database write is performed in this mode.",
        "manifest": manifest_meta,
        "prices": price_meta,
        "erp_probe": erp_state,
        "totals": totals,
        "default_erp_fields_for_new_products": {
            "product_type": "Physical Product",
            "state": "Draft (activate_product is a separate human action)",
            "purchase_price": "0.00 (no supplier cost source)",
            "sale_price": "0.00 when no authoritative retail price; never supplier/pro-forma/cost",
            "pinned_price": "NOT SET (importer never writes a pin; NULL/unset)",
            "effective_price": "sale_price while no pin is present",
            "priced": "false when sale_price=0.00 and no pin",
            "sale_price_website": "0.00 ERP default (website export falls back to sale_price)",
            "vat_rate": "FROM PRICE CSV or flagged unverified ERP default 20.00",
            "description": "NULL", "supplier_id": "NULL",
            "total_sold_website": 0, "total_sold_store": 0,
            "revenue_website": "0.00", "revenue_store": "0.00",
        },
        "price_policy": (
            "Missing/zero retail price is NEEDS PRICING, not a blocker. Import stages "
            "DRAFT products at sale_price=0.00 with no pinned_price; unpriced products "
            "are hidden from sales surfaces until a pin is entered. No price is invented, "
            "inferred, or copied from supplier pro-forma data."
        ),
        "default_erp_fields_for_new_stock_levels": {
            "product_id": "Product.id after flush", "quantity": "manifest.qty",
            "min_quantity": "0 (ERP default)", "stock_movement": "Purchase, +qty, manifest reference",
        },
        "validation": {
            "ok": not all_errors,
            "errors": all_errors,
            "warnings": all_warnings,
        },
        "blockers": all_errors,
        "apply_requires": [
            "--apply",
            "--i-understand-destructive-risk",
            f"{APPROVAL_PATH} containing exactly '{APPROVAL_TEXT}'",
            "an existing ERP database file",
            "a clean validation (zero errors)",
        ],
        "field_map_reference": str(REPO_ROOT / "stock_import" / "erp_field_map.json"),
        "rows": planned_rows,
    }
    return plan


def write_plan(plan: Dict[str, Any]) -> None:
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def print_plan(plan: Dict[str, Any]) -> None:
    totals = plan["totals"]
    validation = plan["validation"]
    print("=== ERP STOCK IMPORT PLAN (DRY RUN - NO DATABASE WRITES) ===")
    print(f"manifest: {plan['manifest'].get('path')}")
    print(f"prices  : {plan['prices'].get('path')}  found={plan['prices'].get('found')}")
    print(f"ERP DB  : {plan['erp_probe'].get('db_path')}  exists={plan['erp_probe'].get('db_exists')}")
    print(
        f"rows={totals['manifest_rows']} units={totals['total_units']} "
        f"products_to_create={totals['products_to_create']} "
        f"matched_by_sku={totals['products_matched_by_sku']} "
        f"unpriced={totals['unpriced_products']} "
        f"priced={totals['priced_products']}"
    )
    print(f"categories_to_create ({len(totals['categories_to_create'])}): {', '.join(totals['categories_to_create']) or '(none)'}")
    print(f"brands_to_create ({len(totals['brands_to_create'])}): {', '.join(totals['brands_to_create']) or '(none)'}")
    print(f"internal_placeholders={totals['internal_placeholders']} rows_requiring_review={totals['rows_requiring_review']}")

    def show_list(title: str, values: List[str]) -> None:
        print(f"{title} ({len(values)}):")
        if not values:
            print("  (none)")
        elif len(values) <= 20:
            for value in values:
                print(f"  - {value}")
        else:
            for value in values[:15]:
                print(f"  - {value}")
            print(f"  ... {len(values) - 15} more (full list: {PLAN_PATH})")

    show_list("PRODUCTS TO CREATE", totals["products_to_create_skus"])
    show_list("PRODUCTS MATCHED BY SKU", totals["products_matched_skus"])

    unpriced = plan["prices"].get("unpriced_skus", [])
    if unpriced:
        show_list("NEEDS PRICING (non-blocking; staged 0.00 / DRAFT / no pin)", unpriced)
        print("  These rows are hidden from sales surfaces until a pin is entered.")
    else:
        print("PRICES: all manifest SKUs have an authoritative retail price")

    if validation["warnings"]:
        print(f"WARNINGS ({len(validation['warnings'])}):")
        for warning in validation["warnings"][:15]:
            print(f"  - {warning}")
        if len(validation["warnings"]) > 15:
            print(f"  ... {len(validation['warnings']) - 15} more (full list: {PLAN_PATH})")
    if validation["errors"]:
        print(f"BLOCKERS ({len(validation['errors'])}) - NOTHING WAS IMPORTED:")
        for error in validation["errors"][:15]:
            print(f"  - {error}")
        if len(validation["errors"]) > 15:
            print(f"  ... {len(validation['errors']) - 15} more (full list: {PLAN_PATH})")
    else:
        print("VALIDATION: OK (plan only; use --apply with both guards to write)")
    print(f"plan written to: {PLAN_PATH}")


def apply_guard_errors(flag: bool, approval_path: Path, plan: Dict[str, Any]) -> List[str]:
    """Checked BEFORE importing ERP modules or opening any DB connection."""
    errors: List[str] = []
    if not flag:
        errors.append(
            "REFUSED: --apply requires --i-understand-destructive-risk "
            "(explicit opt-in flag is absent)"
        )
    if not approval_path.is_file():
        errors.append(
            f"REFUSED: approval file {approval_path} does not exist; it must contain exactly "
            f"'{APPROVAL_TEXT}'"
        )
    else:
        try:
            content = approval_path.read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            errors.append(f"REFUSED: cannot read approval file {approval_path}: {exc}")
        else:
            if content != APPROVAL_TEXT:
                errors.append(
                    f"REFUSED: approval file must contain exactly '{APPROVAL_TEXT}', got {content!r}"
                )
    if not erp_db_path().is_file():
        errors.append(
            f"REFUSED: ERP database {erp_db_path()} does not exist; this tool never creates a database"
        )
    if not plan.get("validation", {}).get("ok", False):
        errors.append(
            "REFUSED: plan has validation blockers (invalid/cost-reference price, "
            "duplicate SKU, bad totals, or unreadable ERP probe); "
            "NEEDS PRICING alone is not a blocker"
        )
    return errors


def run_apply(plan: Dict[str, Any], approval_path: Path, flag: bool) -> int:
    errors = apply_guard_errors(flag, approval_path, plan)
    if errors:
        print("=== APPLY REFUSED - NO DATABASE CONNECTION WAS OPENED, NOTHING WAS WRITTEN ===")
        for error in errors:
            print(f"  - {error}")
        return 3

    # Everything below runs only after both human guards and validation passed.
    try:
        from sqlalchemy import func
        from src.core.context import RequestContext
        from src.core.session import CurrentSession
        from src.database.transaction import transactional
        from src.modules.inventory.models import (
            Brand, Category, Product, ProductState, ProductType, StockLevel, StockMovementType,
        )
        from src.modules.inventory.services import InventoryService
    except Exception as exc:  # pragma: no cover - ERP dependency failure
        print(f"APPLY FAILED before any write (ERP import error): {exc}")
        return 4

    def movement_reference(row: Dict[str, Any]) -> str:
        text = (
            f"stock_import #{row['n']} | {row['ledger']} | p{row['source_page']} | {row['sku']}"
        )
        return text[:100]  # StockMovement.reference is String(100)

    @transactional
    def _import_all(context: RequestContext, import_plan: Dict[str, Any], session=None) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "products_created": 0,
            "products_matched": 0,
            "categories_created": [],
            "brands_created": [],
            "stock_levels_created": 0,
            "stock_increases": 0,
            "stock_already_correct": 0,
            "stock_movements": 0,
            "units_target": import_plan["totals"]["total_units"],
            "products_activated": 0,
            "products_deleted": 0,
        }
        brand_cache: Dict[str, Any] = {}
        category_cache: Dict[str, Any] = {}

        # Additive exact-name get-or-create for lookup rows only.
        for brand_name in sorted({row["brand"] for row in import_plan["rows"]}):
            brand = session.query(Brand).filter(Brand.name == brand_name).first()
            if brand is None:
                brand = Brand(name=brand_name)
                session.add(brand)
                session.flush()
                summary["brands_created"].append(brand_name)
            brand_cache[brand_name] = brand
        for category_name in sorted({row["category"] for row in import_plan["rows"]}):
            category = session.query(Category).filter(Category.name == category_name).first()
            if category is None:
                category = Category(name=category_name)
                session.add(category)
                session.flush()
                summary["categories_created"].append(category_name)
            category_cache[category_name] = category

        touched_product_ids: List[int] = []
        for row in import_plan["rows"]:
            sku = row["sku"]
            product = session.query(Product).filter(Product.sku == sku).first()
            if product is None:
                # sale_price may be 0.00 (NEEDS PRICING). pinned_price is never
                # passed or set by this importer; state stays DRAFT/inactive.
                product = InventoryService.create_product(
                    context,
                    session=session,
                    name=row["name"],
                    sku=sku,
                    product_type=ProductType.PHYSICAL,
                    purchase_price=Decimal("0.00"),
                    sale_price=Decimal(row["price"]["sale_price"]),
                    vat_rate=Decimal(row["price"]["vat_rate"]),
                    brand_id=brand_cache[row["brand"]].id,
                    category_id=category_cache[row["category"]].id,
                )
                summary["products_created"] += 1
                had_level = False
            else:
                # Exact-SKU match: never overwrite name/price/state/brand/category.
                summary["products_matched"] += 1
                had_level = session.query(StockLevel).filter(
                    StockLevel.product_id == product.id
                ).first() is not None

            target = int(row["qty"])
            level = session.query(StockLevel).filter(StockLevel.product_id == product.id).first()
            current = int(level.quantity) if level is not None else 0
            if current > target:
                raise RuntimeError(
                    f"SKU {sku}: existing stock {current} exceeds manifest qty {target}; "
                    "refusing to reduce stock (whole transaction will roll back)"
                )
            if current != target:
                new_qty = InventoryService.adjust_stock(
                    context,
                    session=session,
                    product_id=product.id,
                    quantity_change=target - current,
                    movement_type=StockMovementType.PURCHASE.value,
                    reference=movement_reference(row),
                    enforce_non_negative=True,
                )
                if int(new_qty) != target:
                    raise RuntimeError(f"SKU {sku}: stock ended at {new_qty}, expected {target}; rolling back")
                summary["stock_movements"] += 1
                if had_level:
                    summary["stock_increases"] += 1
                else:
                    summary["stock_levels_created"] += 1
            else:
                summary["stock_already_correct"] += 1
            touched_product_ids.append(product.id)

        # Final in-transaction invariant check: no product is Archived and units are exact.
        actual_units = session.query(func.coalesce(func.sum(StockLevel.quantity), 0)).filter(
            StockLevel.product_id.in_(touched_product_ids)
        ).scalar()
        if int(actual_units or 0) != summary["units_target"]:
            raise RuntimeError(
                f"Post-import unit check failed: {actual_units} != {summary['units_target']}; rolling back"
            )
        unexpected_states = session.query(Product.sku).filter(
            Product.id.in_(touched_product_ids), Product.state != ProductState.DRAFT
        ).count()
        if unexpected_states:
            raise RuntimeError(f"{unexpected_states} product(s) are not Draft; rolling back")
        return summary

    context = RequestContext(
        user_id="0", username="erp_import_tool", role="System", permissions={"Everything"}
    )
    CurrentSession.initialize(context)
    try:
        print("=== APPLY: one transaction; any error rolls back everything ===")
        summary = _import_all(context, plan)
    except Exception as exc:
        print(f"APPLY FAILED - TRANSACTION ROLLED BACK, NO CHANGES COMMITTED: {exc}")
        return 4
    finally:
        CurrentSession.clear()

    print("=== APPLY COMMITTED (rollback-safe summary) ===")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("  products_activated: 0 (activation remains a separate human action)")
    print("  products_deleted: 0 | categories_deleted: 0 | brands_deleted: 0")
    print(f"  approval_file: {approval_path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="default: plan only, no database writes")
    mode.add_argument("--apply", action="store_true", help="DANGEROUS: write ERP data (guarded)")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--prices", type=Path, default=DEFAULT_PRICES,
        help=(
            "OPTIONAL authoritative retail price CSV (sku,sale_price[,vat_rate]); "
            "blank/zero prices are NEEDS PRICING warnings, never inferred or copied "
            "from supplier pro-forma data"
        ),
    )
    parser.add_argument(
        "--i-understand-destructive-risk", action="store_true",
        help="required together with --apply and the approval file",
    )
    args = parser.parse_args(argv)

    plan = build_plan(args.manifest, args.prices)
    write_plan(plan)
    print_plan(plan)

    if args.apply:
        return run_apply(plan, APPROVAL_PATH, args.i_understand_destructive_risk)
    if args.i_understand_destructive_risk:
        print("NOTE: --i-understand-destructive-risk is ignored without --apply (dry-run is safe)")
    if not plan["validation"]["ok"]:
        print("RESULT: BLOCKED - plan written, but validation failed; nothing was imported.")
        return 2
    print("RESULT: PLAN ONLY - no ERP writes performed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
