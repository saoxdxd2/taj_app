#!/usr/bin/env python3
"""Prepare the 3-row pilot catalog payload. DATA PREPARATION ONLY.

This script NEVER pushes anything and makes NO network calls. It only reads the
OPTIONAL operator-supplied price CSV and stock_import/import_manifest.json,
validates them, and (outside --check) writes a local dry-run payload plus a
check report.

PRICE GATE (docs/PINNED_PRICE_CONTRACT.md):
  A blank/zero/missing retail price is a NEEDS PRICING warning, NOT a payload
  error. Unpriced products are staged with sale_price="0", pinned_price="",
  effective_price="0", priced=false and DRAFT/inactive state; they remain
  hidden from sales surfaces until an ERP or phone pin is entered. This tool
  NEVER sets a non-empty pinned_price, NEVER activates an unpriced product,
  and NEVER invents, infers, or copies supplier/pro-forma prices into retail
  sale_price. VAT for an unpriced row may use the ERP default 20.00 with a
  warning; unsafe numeric text and cost/supplier references still fail closed.

IMPORTANT — RELAY PUSH REQUIRES EXPLICIT APPROVAL:
PUT /api/agent/catalog is a FULL REBUILD. The relay executes "DELETE FROM
catalog" before inserting the payload (handlers/agent/catalog/index.go:113-123),
so pushing this 3-product payload would erase every other live catalog row
unless the relay catalog is confirmed empty or the complete intended snapshot
is sent. Confirm relay catalog state and obtain explicit approval before any
push.

Usage:
    python scripts/build_pilot_payload.py --check
    python scripts/build_pilot_payload.py --prices /path/to/approved_prices.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRICES = PROJECT_ROOT / "stock_import" / "prices_template.csv"
MANIFEST_PATH = PROJECT_ROOT / "stock_import" / "import_manifest.json"
PAYLOAD_PATH = PROJECT_ROOT / "stock_import" / "pilot_payload.json"
REPORT_PATH = PROJECT_ROOT / "stock_import" / "pilot_payload_report.json"

PILOT_SKUS = ("UA50DU7000U", "UA43T5300AU", "F710TLG")
EXPECTED_HEADER = ["sku", "sale_price", "vat_rate"]
UNPRICED_SALE_PRICE = "0"
DEFAULT_VAT = "20.00"
PLACEHOLDER_PRICE_VALUES = {"", "-", "n/a", "na", "tbd", "todo", "unknown", "?"}

# Limits enforced by the relay (handlers/agent/catalog/index.go:26-32).
SKU_MAX_RUNES = 128
NAME_MAX_RUNES = 512
TERM_MAX_RUNES = 128
MONEY_MAX_RUNES = 64

NOTE = (
    "DATA PREPARATION ONLY: no push is performed. A relay push now deletes only "
    "SKUs absent from the snapshot and must still be explicitly approved. "
    "Missing prices are NEEDS PRICING warnings; import tooling never sets pinned_price."
)


def add_check(
    checks: list[dict[str, str]], name: str, ok: bool, detail: str,
    status: str | None = None,
) -> bool:
    result = status or ("PASS" if ok else "FAIL")
    checks.append({"name": name, "status": result, "detail": detail})
    return result != "FAIL"


def warn_check(checks: list[dict[str, str]], name: str, detail: str) -> None:
    add_check(checks, name, True, detail, status="WARN")


def skipped(checks: list[dict[str, str]], name: str, why: str) -> None:
    add_check(checks, name, False, "SKIPPED (unsafe to evaluate): " + why)


def has_control_chars(text: str) -> bool:
    return any(unicodedata.category(ch) == "Cc" for ch in text)


def canonical_decimal_text(text: str) -> str:
    """Mirror the relay's canonicalDecimalText (index.go:235-251).

    Mirroring matters: if the generator and the relay canonicalized decimal
    commas differently, a validated value could become a different number in
    the database (e.g. "1,000" must mean 1000 to both sides).
    """
    text = text.strip()
    if "," not in text:
        return text
    if "." in text:
        return text.replace(",", "")
    parts = text.split(",")
    last = parts[-1]
    if 0 < len(last) <= 2:
        return "".join(parts[:-1]) + "." + last
    return text.replace(",", "")


def canonical_money(raw: str, field: str, sku: str) -> tuple[str, Decimal]:
    """Return (canonical decimal string, value) or raise ValueError."""
    text = raw.strip()
    if not text:
        raise ValueError(f"{sku}: {field} is empty")
    canon = canonical_decimal_text(text)
    if not canon:
        raise ValueError(f"{sku}: {field} is empty")
    try:
        value = Decimal(canon)
    except InvalidOperation:
        raise ValueError(f"{sku}: {field} {raw!r} is not a number") from None
    if not value.is_finite():
        raise ValueError(f"{sku}: {field} {raw!r} is not a finite number")
    if value < 0:
        raise ValueError(f"{sku}: {field} {raw!r} must not be negative")
    if value == 0:
        return "0", value
    if value == value.to_integral_value() or "e" in canon.lower():
        out = format(value, "f")
        if "." in out:
            out = out.rstrip("0").rstrip(".")
    else:
        out = canon  # preserve meaningful precision, e.g. "10,50" -> "10.50"
    if len(out) > MONEY_MAX_RUNES:
        raise ValueError(f"{sku}: {field} exceeds {MONEY_MAX_RUNES} characters")
    return out, value


def staged_money(raw: str, field: str, sku: str, default: str) -> tuple[str, Decimal, bool]:
    """Return (canonical text, value, supplied) for an OPTIONAL CSV field.

    Blank/placeholder price or VAT values are not an error: they mean NEEDS
    PRICING. The importer stages a safe explicit default and never invents a
    retail price or copies one from a supplier pro-forma sheet.
    """
    text = (raw or "").strip()
    if text.lower() in PLACEHOLDER_PRICE_VALUES:
        canon, value = canonical_money(default, field, sku)
        return canon, value, False
    return (*canonical_money(text, field, sku), True)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def read_prices(
    path: Path,
    checks: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> dict[str, dict[str, str]]:
    """Parse the OPTIONAL CSV into {sku: {sale_price, vat_rate}} (raw strings)."""
    if not path.is_file():
        warn_check(
            checks, "csv_file_readable",
            f"no file at {display_path(path)}; all pilot SKUs will be staged "
            "NEEDS PRICING (sale_price=0, no pin, DRAFT/inactive)",
        )
        warnings.append(f"NEEDS PRICING: no prices file at {display_path(path)}; no price is invented.")
        return {}
    add_check(checks, "csv_file_readable", True, f"read {display_path(path)}")

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            lines = [
                line for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except (OSError, UnicodeError) as exc:
        add_check(checks, "csv_file_readable", False, f"read failed: {exc}")
        errors.append(f"cannot read prices file: {exc}")
        return {}

    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        add_check(checks, "csv_header_exact", False, "file has no header row")
        errors.append("prices CSV has no header row")
        return {}

    header_ok = [cell.strip() for cell in header] == EXPECTED_HEADER
    add_check(
        checks, "csv_header_exact", header_ok,
        f"expected {EXPECTED_HEADER}, found {header}",
    )
    if not header_ok:
        errors.append(f"prices CSV header must be exactly {','.join(EXPECTED_HEADER)}; found {header}")

    rows: dict[str, dict[str, str]] = {}
    sku_lines: dict[str, list[int]] = {}
    bad_width: list[int] = []
    data_rows = 0
    for row in reader:
        data_rows += 1
        line_no = reader.line_num
        if len(row) != len(EXPECTED_HEADER):
            bad_width.append(line_no)
            errors.append(f"line {line_no}: expected 3 columns, found {len(row)} -> {row!r}")
            continue
        sku = row[0].strip()
        if not sku:
            errors.append(f"line {line_no}: blank SKU in prices CSV")
            continue
        sku_lines.setdefault(sku, []).append(line_no)
        rows.setdefault(sku, {"sale_price": row[1], "vat_rate": row[2], "line": str(line_no)})

    add_check(
        checks, "csv_no_extra_columns", not bad_width,
        "all data rows have exactly 3 columns" if not bad_width
        else f"bad column counts on line(s) {bad_width}",
    )
    if data_rows <= len(PILOT_SKUS):
        add_check(
            checks, "csv_data_rows", True,
            f"found {data_rows} data row(s); 0-3 allowed (absent rows are NEEDS PRICING)",
        )
    else:
        add_check(checks, "csv_data_rows", False, f"found {data_rows} data rows; at most 3 allowed")
        errors.append(f"prices CSV must contain at most 3 data rows; found {data_rows}")

    duplicates = sorted(sku for sku, seen_lines in sku_lines.items() if len(seen_lines) > 1)
    add_check(
        checks, "csv_no_duplicate_skus", not duplicates,
        "each pilot SKU appears at most once" if not duplicates else f"duplicated SKU(s): {duplicates}",
    )
    for sku in duplicates:
        errors.append(f"duplicate SKU in prices CSV: {sku}")

    unknown = sorted(set(rows) - set(PILOT_SKUS))
    add_check(
        checks, "csv_no_unknown_skus", not unknown,
        "no SKU outside the 3 pilot SKUs" if not unknown else f"unknown SKU(s): {unknown}",
    )
    for sku in unknown:
        errors.append(f"unknown SKU in prices CSV: {sku}")

    missing = sorted(set(PILOT_SKUS) - set(rows))
    if missing:
        warn_check(
            checks, "csv_all_pilot_skus_present",
            f"NEEDS PRICING for missing SKU(s): {missing}; they will be staged at 0.00 with no pin",
        )
        warnings.append(f"NEEDS PRICING: no price row for {missing}; no price is invented.")
    else:
        add_check(checks, "csv_all_pilot_skus_present", True, "all 3 pilot SKUs present")

    if not header_ok or bad_width:
        return {}
    return rows


def load_manifest(checks: list[dict[str, str]], errors: list[str]) -> dict[str, dict[str, Any]] | None:
    if not MANIFEST_PATH.is_file():
        add_check(checks, "manifest_readable", False, f"not a file: {MANIFEST_PATH}")
        errors.append(f"manifest not found: {MANIFEST_PATH}")
        return None
    try:
        with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add_check(checks, "manifest_readable", False, f"read/parse failed: {exc}")
        errors.append(f"cannot read manifest: {exc}")
        return None
    add_check(checks, "manifest_readable", True, f"read {display_path(MANIFEST_PATH)}")

    products = data.get("products") if isinstance(data, dict) else None
    if not isinstance(products, list):
        add_check(checks, "manifest_join", False, "manifest has no products list")
        errors.append("manifest has no products list")
        return None

    by_sku: dict[str, dict[str, Any]] = {}
    for product in products:
        if not isinstance(product, dict):
            continue
        sku = product.get("sku")
        if isinstance(sku, str):
            by_sku.setdefault(sku.strip(), product)

    problems: list[str] = []
    for sku in PILOT_SKUS:
        product = by_sku.get(sku)
        if product is None:
            problems.append(f"{sku}: not found in manifest")
            continue
        name = product.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{sku}: missing name in manifest")
        qty = product.get("qty")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
            problems.append(f"{sku}: invalid qty in manifest: {qty!r}")
    add_check(
        checks, "manifest_join", not problems,
        "name/category/brand/qty resolved from manifest for all 3 SKUs" if not problems
        else "; ".join(problems),
    )
    errors.extend(problems)
    return by_sku if not problems else None


def check_relay_limits(
    checks: list[dict[str, str]], errors: list[str], products: list[dict[str, Any]],
) -> None:
    problems: list[str] = []
    for product in products:
        for field, limit in (("sku", SKU_MAX_RUNES), ("name", NAME_MAX_RUNES)):
            value = product[field]
            if len(value) > limit or has_control_chars(value):
                problems.append(f"{product['sku']}: {field} violates relay limit {limit}")
        for field in ("category", "brand"):
            value = product[field]
            if value is not None and (len(value) > TERM_MAX_RUNES or has_control_chars(value)):
                problems.append(f"{product['sku']}: {field} violates relay limit {TERM_MAX_RUNES}")
    add_check(
        checks, "relay_field_limits", not problems,
        "sku/name/category/brand and stock/active fit relay validation" if not problems
        else "; ".join(problems),
    )
    errors.extend(problems)


def build_summary(
    mode: str, prices_path: Path, checks: list[dict[str, str]], errors: list[str],
    warnings: list[str], rows_preview: list[dict[str, Any]],
) -> str:
    status = "PASS" if not errors and all(check["status"] != "FAIL" for check in checks) else "FAIL"
    lines = [
        "=== PILOT CATALOG PAYLOAD - DRY RUN / DATA PREP ONLY (NO PUSH) ===",
        f"prices file : {display_path(prices_path)}",
        f"manifest    : {display_path(MANIFEST_PATH)}",
        f"mode        : {mode}" + (" (read-only: no files written)" if mode == "check" else ""),
        "",
        "VALIDATION CHECKS:",
    ]
    lines.extend(f"  {check['status']:4}  {check['name']}: {check['detail']}" for check in checks)
    lines.append("")
    lines.append("PILOT ROWS (canonical values; pinned_price is always empty):")
    lines.append("  SKU            SALE  EFFECTIVE  PINNED  PRICED  VAT    STOCK  BRAND     CATEGORY")
    for row in rows_preview:
        lines.append(
            f"  {row['sku']:<14} {str(row['sale_price'] or '-'):<4} "
            f"{str(row['effective_price'] or '-'):<9} "
            f"{str(row['pinned_price'] if row['pinned_price'] is not None else '-'):<6} "
            f"{str(row['priced'] if row['priced'] is not None else '-'):<6} "
            f"{str(row['vat_rate'] or '-'):<5} {str(row['stock'] or '-'):<5} "
            f"{str(row['brand'] or '-'):<8} {row['category'] or '-'}"
        )
    lines.append("")
    if warnings:
        lines.append("NEEDS PRICING / WARNINGS:")
        lines.extend(f"  - {warning}" for warning in warnings)
        lines.append("")
    if errors:
        lines.append("ERRORS:")
        lines.extend(f"  - {error}" for error in errors)
        lines.append("")
    lines.append(
        f"RESULT: {status} ({len(errors)} error(s), {len(warnings)} warning(s))."
        + (" No payload or report written." if mode == "check" else
           " Payload written only when no check fails." if status == "PASS" else
           " No payload written because validation failed.")
    )
    lines.append("REMINDER: " + NOTE)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--prices", type=Path, default=DEFAULT_PRICES,
        help=(
            "OPTIONAL CSV with sku,sale_price,vat_rate (default: "
            "stock_import/prices_template.csv); blank/zero prices are NEEDS "
            "PRICING warnings, not errors, and no price is inferred or copied"
        ),
    )
    parser.add_argument(
        "--check", action="store_true",
        help="validate input only; write no payload and no report (read-only)",
    )
    args = parser.parse_args(argv)

    mode = "check" if args.check else "build"
    prices_path = args.prices.resolve()
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []
    rows_preview: list[dict[str, Any]] = [
        {
            "sku": sku, "sale_price": "", "effective_price": "", "pinned_price": "",
            "priced": False, "vat_rate": "", "stock": "", "brand": "", "category": "",
        }
        for sku in PILOT_SKUS
    ]

    price_rows = read_prices(prices_path, checks, errors, warnings)
    manifest_by_sku = load_manifest(checks, errors)

    products: list[dict[str, Any]] = []
    version: int | None = None
    inputs_ok = (
        not errors and all(check["status"] != "FAIL" for check in checks)
    )

    if inputs_ok and manifest_by_sku is not None:
        canonical: dict[str, dict[str, Any]] = {}
        needs_pricing = 0
        for sku in PILOT_SKUS:
            raw = price_rows.get(sku, {})
            parsed: dict[str, str] = {}
            values: dict[str, Decimal] = {}
            row_errors: list[str] = []
            try:
                sale_text, sale_value, sale_supplied = staged_money(
                    raw.get("sale_price", ""), "sale_price", sku, UNPRICED_SALE_PRICE
                )
                vat_text, vat_value, vat_supplied = staged_money(
                    raw.get("vat_rate", ""), "vat_rate", sku, DEFAULT_VAT
                )
            except ValueError as exc:
                row_errors.append(str(exc))
            else:
                if not (Decimal(0) <= vat_value <= Decimal(100)):
                    row_errors.append(f"{sku}: vat_rate must be in 0..100 (got {raw.get('vat_rate')!r})")
                if not sale_supplied or sale_value == 0:
                    needs_pricing += 1
                    warnings.append(
                        f"NEEDS PRICING: {sku} staged at sale_price={sale_text}, "
                        "pinned_price='', effective_price=0, priced=false, DRAFT/inactive; "
                        "enter a retail price/pin later from an authoritative source."
                    )
                if not vat_supplied:
                    warnings.append(
                        f"NEEDS PRICING: {sku} VAT not supplied; staged ERP default "
                        f"{vat_text} until the verified rate is entered."
                    )
                parsed = {"sale_price": sale_text, "vat_rate": vat_text}
                values = {"sale_price": sale_value, "vat_rate": vat_value}
            errors.extend(row_errors)
            if not row_errors:
                canonical[sku] = {"text": parsed, "value": values}
        add_check(
            checks, "csv_prices_canonicalized", len(canonical) == 3,
            "all 6 price/VAT values are finite, non-negative, canonical and in range; "
            "blank values staged explicitly (never inferred)" if len(canonical) == 3
            else f"only {len(canonical)}/3 SKUs have usable price/VAT values",
        )
        if needs_pricing:
            warn_check(
                checks, "unpriced_rows_are_warnings",
                f"{needs_pricing}/3 SKU(s) are NEEDS PRICING; imported as 0.00 / no pin / DRAFT "
                "and hidden from sales surfaces until priced",
            )
        else:
            add_check(
                checks, "unpriced_rows_are_warnings", True,
                "all 3 pilot SKUs have authoritative retail prices",
            )

        if len(canonical) == 3:
            for sku in PILOT_SKUS:
                source = manifest_by_sku[sku]
                texts = canonical[sku]["text"]
                sale_value = canonical[sku]["value"]["sale_price"]
                priced = sale_value > 0
                product = {
                    "sku": sku,
                    "name": source["name"],
                    "sale_price": texts["sale_price"],
                    "pinned_price": "",
                    "effective_price": texts["sale_price"],
                    "priced": priced,
                    "vat_rate": texts["vat_rate"],
                    "stock": int(source["qty"]),
                    "active": priced,
                    "category": source.get("category"),
                    "brand": source.get("brand"),
                }
                products.append(product)
                preview = next(row for row in rows_preview if row["sku"] == sku)
                preview.update({
                    "sale_price": product["sale_price"],
                    "effective_price": product["effective_price"],
                    "pinned_price": product["pinned_price"],
                    "priced": product["priced"],
                    "vat_rate": product["vat_rate"],
                    "stock": product["stock"],
                    "brand": product["brand"] or "",
                    "category": product["category"] or "",
                })
            check_relay_limits(checks, errors, products)
            digest = hashlib.sha256(json.dumps(products, sort_keys=True).encode()).hexdigest()
            version = int(digest[:8], 16)
            expected_keys = {
                "sku", "name", "sale_price", "pinned_price", "effective_price", "priced",
                "vat_rate", "stock", "active", "category", "brand",
            }
            shape_ok = (
                len(products) == 3
                and all(set(product) == expected_keys for product in products)
                and all(isinstance(product["stock"], int) and product["stock"] >= 0
                        for product in products)
                and all(product["pinned_price"] == "" for product in products)
                and all(product["effective_price"] == product["sale_price"] for product in products)
                and all(product["priced"] == (Decimal(product["sale_price"]) > 0)
                        for product in products)
                and all(product["active"] == product["priced"] for product in products)
                and isinstance(version, int) and version >= 0
            )
            add_check(
                checks, "payload_shape", shape_ok,
                f"version={version}, baseRevision=0, 3 products with exact contract keys; "
                "pinned_price always '' and never set by import tooling"
                if shape_ok else "payload keys/values do not match the pinned-price contract",
            )
            add_check(
                checks, "version_formula", version == int(
                    hashlib.sha256(json.dumps(products, sort_keys=True).encode()).hexdigest()[:8], 16
                ),
                "version = int(sha256(json.dumps(products, sort_keys=True))[:8], 16)",
            )
    else:
        for name in (
            "csv_prices_canonicalized", "unpriced_rows_are_warnings", "relay_field_limits",
            "payload_shape", "version_formula",
        ):
            skipped(checks, name, "prices CSV or manifest validation did not pass")

    all_ok = bool(products) and not errors and all(check["status"] != "FAIL" for check in checks)
    print(build_summary(mode, prices_path, checks, errors, warnings, rows_preview))

    report: dict[str, Any] = {
        "generated_by": "scripts/build_pilot_payload.py",
        "mode": mode,
        "prices_file": display_path(prices_path),
        "manifest_file": display_path(MANIFEST_PATH),
        "status": "PASS" if all_ok else "FAIL",
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "pilot_rows": rows_preview,
        "payload_file": display_path(PAYLOAD_PATH) if all_ok and mode == "build" else None,
        "note": NOTE,
    }

    if mode == "check":
        # Read-only mode: never write a payload, a report, or any other file.
        return 0 if all_ok else 1

    try:
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {display_path(REPORT_PATH)}")
    except OSError as exc:
        print(f"ERROR: cannot write report: {exc}", file=sys.stderr)
        return 1

    if not all_ok:
        return 1

    # Final hard guard: a staged payload may be unpriced, but must never set a
    # pin, invent an effective price, or activate unpriced stock.
    for product in products:
        if product["pinned_price"] != "" or product["effective_price"] != product["sale_price"]:
            print(f"ERROR: refusing to write payload: invalid pinned/effective price for {product['sku']}", file=sys.stderr)
            return 1
        if product["active"] and Decimal(product["sale_price"]) <= 0:
            print(f"ERROR: refusing to write payload: unpriced product is active: {product['sku']}", file=sys.stderr)
            return 1

    payload = {"version": version, "baseRevision": 0, "products": products}
    try:
        PAYLOAD_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {display_path(PAYLOAD_PATH)}")
    except OSError as exc:
        print(f"ERROR: cannot write payload: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
