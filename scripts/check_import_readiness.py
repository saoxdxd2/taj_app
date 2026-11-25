#!/usr/bin/env python3
"""Strict go/no-go gate for the TAJ FROID stock import (agent L).

Writes stock_import/import_readiness.json and exits 1 if any hard blocker is
present. It only READS the existing audit artifacts. The human-input files
below are deliberately NOT created by this script:

  stock_import/prices.csv               OPTIONAL authoritative retail prices
  stock_import/label_confirmations.json explicit real-SKU confirmation for 8 placeholders
  stock_import/decision_queue.json      resolved human decisions (including #39/#40)
  stock_import/SOURCE_ERRATA.md         acknowledgement of the 95/55 status split
  stock_import/APPLY_APPROVED.txt       explicit approval for --apply / relay push

PRICE GATE (per docs/PINNED_PRICE_CONTRACT.md):
  A missing price CSV, a blank/zero sale_price, or an unconfirmed VAT rate on
  an unpriced row is a NEEDS PRICING warning, NOT an import blocker. The import
  may create DRAFT products with sale_price=0.00 and no pinned_price; a later
  pin from the ERP or phone makes them sellable. Unpriced products stay hidden
  from sales surfaces until then. This script never invents, infers, or copies
  supplier/pro-forma prices into retail sale_price and never sets pinned_price.
  Invalid numeric text, negative values, formula fragments, duplicate/malformed
  price rows, and cost/supplier reference fields remain hard blockers.

Scope semantics:
  --scope full   validate all 150 manifest SKUs; the push itself is the full
                 snapshot, so the relay DELETE-all rebuild is inherently safe.
  --scope pilot  validate exactly the 3 pilot SKUs. Because PUT /api/agent/catalog
                 deletes the whole catalog first, a pilot push ALSO requires
                 --relay-empty (a fresh assertion that production is empty) or a
                 verified full snapshot via --relay-snapshot. If a full snapshot
                 is supplied, the price check is widened to every SKU in it,
                 since that snapshot is what would be pushed.

Program-level human gates (label confirmations, all unresolved decisions,
#39/#40 decision, errata and explicit import/push approval) are global gates
and are required for BOTH scopes. Dry-run planning is always allowed.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOCK = ROOT / "stock_import"

MANIFEST_PATH = STOCK / "import_manifest.json"
PRICES_PATH = STOCK / "prices.csv"
LABELS_PATH = STOCK / "label_confirmations.json"
DECISIONS_PATH = STOCK / "decision_queue.json"
ERRATA_PATH = STOCK / "SOURCE_ERRATA.md"
APPROVAL_PATH = STOCK / "APPLY_APPROVED.txt"
FLAGS_PATH = STOCK / "verify_flags.json"
TOTALS_PATH = STOCK / "verify_totals.json"
DEDUP_PATH = STOCK / "verify_dedup.json"
DEFAULT_SNAPSHOT_PATH = STOCK / "relay_snapshot.json"
APPROVAL_TEXT = "APPROVED BY HUMAN"

PILOT_SKUS = ("UA50DU7000U", "UA43T5300AU", "F710TLG")
PLACEHOLDER_ROWS = (86, 120, 125, 126, 134, 135, 138, 149)
DUPLICATE_PAIR = (39, 40)
EXPECTED_ROWS = 149
EXPECTED_UNITS = 297
MERGED_AWAY_ROWS = (40,)

COST_RE = re.compile(
    r"supplier|pro[\s-]?forma|cost|purchase|wholesale|discount|"
    r"tarif|fournisseur|achat|prix\s+unitaire",
    re.I,
)
COST_KEY_RE = re.compile(
    r"cost|supplier|pro[\s-]?forma|purchase|wholesale|discount|"
    r"tarif|fournisseur|achat",
    re.I,
)
NOTE_KEY_RE = re.compile(r"source|basis|kind|note|price_type|reference", re.I)
NON_NUMERIC_RE = re.compile(r"[^\d.,]")
PLACEHOLDER_VALUE_RE = re.compile(r"^(\[no code\]|n/?a|tbd|todo|unknown|-+|\?+|pending)$", re.I)


def read_json(path: Path):
    """Return (data, error). error is a human-readable string or None."""
    if not path.exists():
        return None, "MISSING file: %s" % relative(path)
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle), None
    except (OSError, ValueError) as exc:
        return None, "UNREADABLE file: %s (%s)" % (relative(path), exc)


def read_text(path: Path):
    if not path.exists():
        return None, "MISSING file: %s" % relative(path)
    try:
        return path.read_text(encoding="utf-8-sig"), None
    except OSError as exc:
        return None, "UNREADABLE file: %s (%s)" % (relative(path), exc)


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"\s*\d+\s*", value):
        return int(value)
    return None


def clean(value) -> str:
    return "" if value is None else str(value).strip()


def is_placeholder_value(value) -> bool:
    text = clean(value)
    return not text or bool(PLACEHOLDER_VALUE_RE.fullmatch(text)) or text.upper().startswith("PH-")


def label_entries(labels) -> dict:
    """Index confirmations by row number; accept a root list, rows, confirmations or entries."""
    if isinstance(labels, dict):
        items = []
        for key in ("rows", "confirmations", "entries"):
            if isinstance(labels.get(key), list):
                items = labels[key]
                break
    else:
        items = labels
    if not isinstance(items, list):
        return {}
    indexed = {}
    for item in items:
        if isinstance(item, dict):
            n = as_int(item.get("n"))
            if n is not None:
                indexed.setdefault(n, []).append(item)
    return indexed


def effective_skus(manifest, labels) -> tuple[dict, list]:
    """Map row n -> effective SKU (confirmed real SKU if confirmed, else manifest SKU)."""
    products = manifest.get("products", []) if isinstance(manifest, dict) else []
    confirmed = label_entries(labels)
    result = {}
    problems = []
    for product in products:
        if not isinstance(product, dict):
            continue
        n = as_int(product.get("n"))
        if n is None:
            problems.append("row with non-integer n")
            continue
        sku = clean(product.get("sku"))
        entries = confirmed.get(n, [])
        if entries and not is_placeholder_value(entries[0].get("confirmed_real_sku")):
            sku = clean(entries[0].get("confirmed_real_sku"))
        result[n] = sku
    return result, problems


def parse_prices():
    """Return (rows_by_sku, all_rows, error).

    A missing price file is not an error: unpriced products are allowed by the
    pinned-price contract. A present-but-malformed file is still fail-closed.
    """
    if not PRICES_PATH.exists():
        return {}, [], None
    try:
        with PRICES_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = [clean(h).lower().replace(" ", "_") for h in (reader.fieldnames or [])]
            required_headers = {"sku", "sale_price", "vat_rate"}
            missing_headers = sorted(required_headers - set(headers))
            if missing_headers:
                return {}, [], "INVALID header in %s: missing %s; required header is 'sku,sale_price,vat_rate'." % (
                    relative(PRICES_PATH), ", ".join(missing_headers)
                )
            rows = []
            for raw in reader:
                normalized = {}
                for key, value in raw.items():
                    if key is None:
                        continue
                    normalized[clean(key).lower().replace(" ", "_")] = value
                if not any(clean(v) for v in normalized.values()):
                    continue
                rows.append(normalized)
    except (OSError, csv.Error, UnicodeError) as exc:
        return {}, [], "UNREADABLE file: %s (%s)" % (relative(PRICES_PATH), exc)

    by_sku = {}
    duplicates = []
    for row in rows:
        sku = clean(row.get("sku"))
        if not sku:
            duplicates.append("<blank SKU>")
            continue
        if sku in by_sku:
            duplicates.append(sku)
        else:
            by_sku[sku] = row
    if duplicates:
        return {}, rows, "DUPLICATE SKU rows in %s: %s. Keep exactly one authoritative row per SKU." % (
            relative(PRICES_PATH), ", ".join(sorted(set(duplicates)))
        )
    return by_sku, rows, None


def normalize_decimal(raw):
    """Return Decimal for a plain number, accepting comma decimal and common currency marks."""
    text = clean(raw)
    text = re.sub(r"(?i)\b(dh|mad|eur|€)\b", "", text)
    text = text.replace("\u00a0", " ").replace(" ", "")
    if text.count(",") == 1 and "." not in text:
        text = text.replace(",", ".")
    if not re.fullmatch(r"\+?\d+(?:\.\d+)?", text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def price_issue(row) -> tuple[str, str | None]:
    """Classify a price row as ('ok'|'needs_pricing'|'block', reason).

    Blank/zero retail prices are NEEDS PRICING: the import creates a DRAFT
    product with sale_price=0.00 and no pin. Everything unsafe (negative,
    non-numeric, formula, cost/supplier reference) remains a hard blocker.
    """
    for key, val in row.items():
        text = clean(val)
        if not text:
            continue
        if COST_KEY_RE.search(key):
            return "block", "row has a cost/supplier field '%s'=%r; supplier costs must not become sale_price" % (key, text)
        if NOTE_KEY_RE.search(key) and COST_RE.search(text):
            return "block", "row field '%s'=%r marks a supplier/pro-forma/cost source; use an authoritative retail price" % (key, text)

    raw = clean(row.get("sale_price"))
    if not raw or PLACEHOLDER_VALUE_RE.fullmatch(raw):
        return "needs_pricing", "blank/default sale_price (import will stage 0.00 / DRAFT / no pin)"
    if re.search(r"[-/<>=%()]|->", raw):
        return "block", "sale_price %r is a formula/range/discount fragment, not a plain retail price" % raw
    letters = re.sub(r"(?i)\b(dh|mad|eur|€)\b", "", raw)
    if re.search(r"[A-Za-z\u00e9\u00e8]", letters):
        return "block", "sale_price %r contains non-numeric text; enter a plain authoritative retail price" % raw
    if NON_NUMERIC_RE.sub("", raw).count(",") > 1:
        return "block", "sale_price %r has ambiguous separators; use a plain decimal such as 1299.00" % raw
    value = normalize_decimal(raw)
    if value is None:
        return "block", "sale_price %r is not a valid decimal" % raw
    if value < 0:
        return "block", "sale_price %r is negative; negative prices are never importable" % raw
    if value == 0:
        return "needs_pricing", "sale_price is zero; stage as unpriced (0.00 / DRAFT / no pin) and price later"
    if value <= 1:
        return "block", "sale_price %r looks like a supplier discount factor/cost reference, not a retail price" % raw
    return "ok", None


def vat_problem(row) -> str | None:
    raw = clean(row.get("vat_rate"))
    if not raw or PLACEHOLDER_VALUE_RE.fullmatch(raw):
        return "blank/default vat_rate (relay would silently substitute 20)"
    if raw.rstrip().endswith("%"):
        raw = raw.rstrip()[:-1]
    value = normalize_decimal(raw)
    if value is None:
        return "vat_rate %r is not numeric; enter the verified rate (e.g. 20)" % clean(row.get("vat_rate"))
    if not (0 < value <= 100):
        return "vat_rate %r is outside (0, 100]; the relay fallback is 20, so an unverified value is unsafe" % clean(row.get("vat_rate"))
    return None


def snapshot_sku_set(arg_path: str | None):
    """Validate a full relay snapshot file; return (skus, note, error)."""
    path = Path(arg_path) if arg_path else DEFAULT_SNAPSHOT_PATH
    if not path.is_absolute() and not path.exists():
        candidate = ROOT / path
        if candidate.exists():
            path = candidate
    if not path.exists():
        return set(), "no full snapshot at %s" % relative(path), None
    data, error = read_json(path)
    if error:
        return set(), "", "Full snapshot unusable: %s. Replace it with a JSON file containing every catalog SKU." % error
    if isinstance(data, dict):
        items = None
        for key in ("products", "catalog", "rows", "skus"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
        if items is None:
            return set(), "", "Full snapshot %s has no products/catalog/rows/skus list." % relative(path)
    elif isinstance(data, list):
        items = data
    else:
        return set(), "", "Full snapshot %s must be a JSON object or list." % relative(path)
    skus = set()
    for item in items:
        sku = clean(item.get("sku")) if isinstance(item, dict) else clean(item)
        if not sku:
            return set(), "", "Full snapshot %s has an entry without a sku." % relative(path)
        skus.add(sku)
    return skus, "verified full snapshot %s (%d SKUs)" % (relative(path), len(skus)), None


def pair_entries(decisions) -> list:
    """Find entries covering both rows #39 and #40 in any common queue layout."""
    if isinstance(decisions, dict):
        items = []
        for key in ("decisions", "queue", "items", "rows", "entries"):
            if isinstance(decisions.get(key), list):
                items = decisions[key]
                break
        if not items and isinstance(decisions.get("groups"), list):
            for group in decisions["groups"]:
                if not isinstance(group, dict):
                    continue
                for key in ("entries", "items", "decisions"):
                    nested = group.get(key)
                    if isinstance(nested, list):
                        items.extend(nested)
                        break
                else:
                    items.append(group)
    else:
        items = decisions
    if not isinstance(items, list):
        return []
    found = []
    for item in items:
        if not isinstance(item, dict):
            continue
        numbers = set()
        for key in ("n", "row", "row_n", "number"):
            value = item.get(key)
            parsed = as_int(value)
            if parsed is not None:
                numbers.add(parsed)
            else:
                for match in re.findall(r"(?<![0-9])#?(\d+)(?![0-9])", clean(value)):
                    numbers.add(int(match))
        for key in ("pair", "rows", "row_numbers", "pair_with", "ids", "covered_rows"):
            value = item.get(key)
            values = value if isinstance(value, list) else [value]
            for entry in values:
                parsed = as_int(entry.get("n")) if isinstance(entry, dict) else as_int(entry)
                if parsed is not None:
                    numbers.add(parsed)
        if not {39, 40}.issubset(numbers):
            text = " ".join(clean(item.get(k)) for k in (
                "id", "pair", "pair_id", "issue", "name", "description", "note", "question",
                "sku", "status", "ledger", "covered_rows"
            ))
            if re.search(r"(?<![0-9])#?39(?![0-9])", text) and re.search(r"(?<![0-9])#?40(?![0-9])", text):
                found.append(item)
        else:
            found.append(item)
    return found


def pair_is_resolved(entry) -> bool:
    if entry.get("blocks_import") is True or clean(entry.get("blocks_import")).lower() == "true":
        return False
    for key in ("resolved", "is_resolved"):
        if key in entry:
            value = entry[key]
            return value is True or clean(value).lower() in {"true", "yes", "1"}
    status = clean(entry.get("status")).lower()
    if status in {"unresolved", "pending", "open", "deferred", "awaiting", "awaiting human decisions"}:
        return False
    if status in {"resolved", "decided", "closed", "done", "complete"}:
        return True
    # A filled-in non-placeholder decision IS the resolution in the human queue layout.
    return bool(pair_decision_text(entry))


def pair_decision_text(entry) -> str:
    for key in ("decision", "resolution", "outcome", "resolution_note"):
        value = clean(entry.get(key))
        if value and not PLACEHOLDER_VALUE_RE.fullmatch(value):
            return value
    return ""


def all_decision_entries(decisions) -> list:
    """Return every human queue entry, including entries nested under groups."""
    if isinstance(decisions, dict):
        items = []
        for key in ("decisions", "queue", "items", "rows", "entries"):
            if isinstance(decisions.get(key), list):
                items = decisions[key]
                break
        if not items and isinstance(decisions.get("groups"), list):
            for group in decisions["groups"]:
                if not isinstance(group, dict):
                    continue
                for key in ("entries", "items", "decisions"):
                    nested = group.get(key)
                    if isinstance(nested, list):
                        items.extend(nested)
                        break
                else:
                    items.append(group)
    else:
        items = decisions
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def decision_is_resolved(entry) -> bool:
    """A human decision needs a filled decision, decidant and timestamp."""
    return all(
        not is_placeholder_value(entry.get(key))
        for key in ("decision", "decided_by", "decided_at")
    )


def explicit_approval_problems() -> list:
    """The import/push approval is a global blocker; dry-run needs no approval."""
    if not APPROVAL_PATH.is_file():
        return [
            "MISSING file: %s. Create it with exactly '%s' before any --apply or relay push; "
            "dry-run planning does not require it." % (relative(APPROVAL_PATH), APPROVAL_TEXT)
        ]
    try:
        content = APPROVAL_PATH.read_text(encoding="utf-8-sig").strip()
    except OSError as exc:
        return ["UNREADABLE file: %s (%s)" % (relative(APPROVAL_PATH), exc)]
    if content != APPROVAL_TEXT:
        return ["%s must contain exactly '%s' (found %r)." % (relative(APPROVAL_PATH), APPROVAL_TEXT, content)]
    return []


def discrepancy_warnings(data, filename) -> list:
    if not isinstance(data, dict):
        return []
    return ["%s discrepancy: %s" % (filename, clean(item)) for item in data.get("discrepancies", []) if clean(item)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scope", choices=("pilot", "full"), required=True)
    parser.add_argument("--relay-empty", action="store_true", help="Assert that a FRESH direct DB query just confirmed the production relay catalog is empty. Required for an un-snapshotted pilot push.")
    parser.add_argument("--relay-snapshot", default=None, help="Path to a verified full relay catalog snapshot (JSON). Used for pilot scope instead of --relay-empty.")
    args = parser.parse_args()
    scope = args.scope

    manifest, manifest_err = read_json(MANIFEST_PATH)
    labels, labels_err = read_json(LABELS_PATH)
    decisions, decisions_err = read_json(DECISIONS_PATH)
    flags, flags_err = read_json(FLAGS_PATH)
    totals, totals_err = read_json(TOTALS_PATH)
    dedup, dedup_err = read_json(DEDUP_PATH)
    errata_text, errata_err = read_text(ERRATA_PATH)
    price_rows, price_all_rows, price_err = parse_prices()
    snapshot_skus, snapshot_note, snapshot_error = snapshot_sku_set(args.relay_snapshot)

    checks = []
    warnings = []
    needs_pricing = []

    def add_check(name, ok, detail, status=None):
        result = status or ("PASS" if ok else "FAIL")
        checks.append({"name": name, "result": result, "detail": detail.strip()})
        return result != "FAIL"

    def add_warning_check(name, detail):
        add_check(name, True, detail, status="WARN")

    # 1. Manifest invariants -------------------------------------------------
    problems = []
    if manifest_err:
        problems.append(manifest_err + " Regenerate it with scripts/build_import_manifest.py.")
    else:
        products = manifest.get("products", []) if isinstance(manifest, dict) else []
        if not isinstance(products, list):
            problems.append("%s has no products list." % relative(MANIFEST_PATH))
            products = []
        nums = [as_int(p.get("n")) for p in products if isinstance(p, dict)]
        if len(products) != EXPECTED_ROWS or len(nums) != EXPECTED_ROWS:
            problems.append("%s must contain %d product rows (found %d)." % (relative(MANIFEST_PATH), EXPECTED_ROWS, len(products)))
        expected_nums = [i for i in range(1, 151) if i not in MERGED_AWAY_ROWS]
        if nums != expected_nums:
            missing_n = sorted(set(expected_nums) - set(nums))
            extra_n = sorted(n for n in nums if n not in set(expected_nums))
            dup_n = sorted({n for n in nums if nums.count(n) > 1 and n is not None})
            problems.append("row numbers do not match merged 1..150 (excluding %s) (missing=%s, unexpected=%s, repeated=%s)." % (list(MERGED_AWAY_ROWS), missing_n, extra_n, dup_n))
        units = 0
        bad_qty = []
        for product in products:
            if not isinstance(product, dict):
                bad_qty.append("<non-object row>")
                continue
            qty = as_int(product.get("qty"))
            if qty is None:
                bad_qty.append("n=%s" % product.get("n"))
            else:
                units += qty
        if bad_qty:
            problems.append("invalid qty for rows %s." % ", ".join(map(str, bad_qty[:10])))
        if units != EXPECTED_UNITS:
            problems.append("qty sum is %d, expected %d." % (units, EXPECTED_UNITS))
        if isinstance(manifest, dict):
            for field, expected in (("rows", EXPECTED_ROWS), ("units", EXPECTED_UNITS)):
                declared = as_int(manifest.get(field))
                if declared != expected:
                    problems.append("declared '%s' is %s, expected %d." % (field, declared, expected))
        sku_map, sku_problems = effective_skus(manifest, labels)
        problems.extend(sku_problems)
        seen = {}
        for n, sku in sku_map.items():
            if not sku:
                problems.append("row %d has no effective SKU." % n)
            key = sku.casefold()
            if key in seen:
                problems.append("effective SKU %r duplicated on rows %d and %d." % (sku, seen[key], n))
            else:
                seen[key] = n
        placeholder_rows = tuple(sorted(
            as_int(p.get("n")) for p in products
            if isinstance(p, dict) and (p.get("internal_placeholder") is True or clean(p.get("original_sku")) == "[No code]")
            and as_int(p.get("n")) is not None
        ))
        if placeholder_rows != PLACEHOLDER_ROWS:
            problems.append("internal placeholder rows are %s, expected %s." % (list(placeholder_rows), list(PLACEHOLDER_ROWS)))
    add_check(
        "manifest_invariants",
        not problems,
        "%s: %d rows / %d units / merged #40->#39 / %d unique effective SKUs." % (relative(MANIFEST_PATH), EXPECTED_ROWS, EXPECTED_UNITS, len({s.casefold() for s in (effective_skus(manifest, labels)[0].values())}))
        if not problems else "Fix %s: %s" % (relative(MANIFEST_PATH), " ".join(problems)),
    )

    # 2. Prices are OPTIONAL: missing/zero is NEEDS PRICING, not a blocker ----
    # A specified-but-invalid snapshot file is a hard safety error (check 6), not a silent fallback.
    snapshot_used = scope == "pilot" and bool(snapshot_skus) and not snapshot_error
    pilot_exact = scope == "pilot" and not snapshot_used
    if scope == "full":
        required = set(effective_skus(manifest, labels)[0].values()) if not manifest_err else set()
        scope_label = "all 150 manifest SKUs"
    elif snapshot_used:
        required = set(snapshot_skus)
        scope_label = "all %d SKUs in the supplied full snapshot" % len(snapshot_skus)
        warnings.append("Pilot scope with a full snapshot: the price check was widened to every snapshot SKU. Confirm the PUT payload is exactly that snapshot.")
    else:
        required = set(PILOT_SKUS)
        scope_label = "exactly the 3 pilot SKUs (%s)" % ", ".join(PILOT_SKUS)

    price_structure_problems = []
    bad_prices = []
    bad_vat = []
    unpriced_rows = set()
    if price_err:
        price_structure_problems.append(price_err)
    else:
        if pilot_exact:
            extra = sorted(set(price_rows) - required)
            if extra:
                warnings.append("%s has %d extra SKU(s) outside pilot scope (ignored): %s." % (
                    relative(PRICES_PATH), len(extra), ", ".join(extra[:20]) + (" ..." if len(extra) > 20 else "")
                ))
        elif scope == "full":
            extra = sorted(set(price_rows) - required)
            if extra:
                warnings.append("%s contains %d SKU(s) not in the manifest: %s." % (relative(PRICES_PATH), len(extra), ", ".join(extra[:10])))
        for row in price_all_rows:
            sku = clean(row.get("sku")) or "<blank SKU>"
            kind, reason = price_issue(row)
            if kind == "needs_pricing":
                unpriced_rows.add(sku)
            elif kind == "block":
                bad_prices.append("%s: %s" % (sku, reason))
        # VAT is only required once a row has a real retail price. An unpriced
        # row may use the ERP default 20.00 until the product is pinned.
        for sku in sorted((required & set(price_rows)) - unpriced_rows):
            vat_note = vat_problem(price_rows[sku])
            if vat_note:
                bad_vat.append("%s: %s" % (sku, vat_note))

    unpriced = sorted((required - set(price_rows)) | (required & unpriced_rows)) if not price_err else []
    coverage_failure = price_structure_problems + bad_vat
    coverage_detail = ""
    if unpriced:
        sample = ", ".join(unpriced[:20]) + (" ..." if len(unpriced) > 20 else "")
        source = (
            "no price file at %s" % relative(PRICES_PATH) if not PRICES_PATH.exists()
            else "%s" % relative(PRICES_PATH)
        )
        coverage_detail = (
            "NEEDS PRICING (non-blocking) for %d/%d SKU(s) (%s): %s. Import stages "
            "sale_price=0.00, pinned_price unset, state DRAFT; a later ERP/phone pin makes "
            "them sellable. No price is invented or copied from supplier pro-forma data."
        ) % (len(unpriced), len(required), source, sample or "(none)")
        needs_pricing.append(coverage_detail)
        warnings.append(coverage_detail)
    if coverage_failure:
        add_check(
            "price_coverage", False,
            "Resolve unsafe price data before pushing: " + " ".join(coverage_failure),
        )
    elif unpriced:
        add_warning_check("price_coverage", coverage_detail)
    else:
        add_check(
            "price_coverage", True,
            "%s has authoritative retail prices for %s." % (relative(PRICES_PATH), scope_label),
        )

    if bad_prices:
        add_check(
            "prices_not_default_or_cost_reference", False,
            "Edit %s - %s" % (relative(PRICES_PATH), "; ".join(bad_prices[:12]) + (" ..." if len(bad_prices) > 12 else "")),
        )
    else:
        safety_detail = (
            "No price file present; no unsafe values to reject."
            if not PRICES_PATH.exists() else
            "No negative, formula, non-numeric or cost/pro-forma reference values in %s "
            "(%d row(s) checked)." % (relative(PRICES_PATH), len(price_all_rows))
        )
        add_check(
            "prices_not_default_or_cost_reference", True,
            safety_detail + " Blank/zero rows are NEEDS PRICING warnings, not blockers.",
        )

    # 4. Human confirmation of the 8 internal placeholder labels -------------
    label_problems = []
    if labels_err:
        label_problems.append(labels_err + " A human must create it with one explicit {'n': ..., 'confirmed_real_sku': '...', 'confirmed_by': '...'} entry for each of rows %s." % (", ".join(map(str, PLACEHOLDER_ROWS))))
    else:
        indexed = label_entries(labels)
        for n in PLACEHOLDER_ROWS:
            entries = indexed.get(n, [])
            if not entries:
                label_problems.append("no explicit entry for row %d" % n)
                continue
            entry = entries[0]
            for field in ("confirmed_real_sku", "confirmed_by"):
                if is_placeholder_value(entry.get(field)):
                    label_problems.append("row %d has no non-empty '%s'" % (n, field))
    add_check(
        "placeholder_label_confirmations",
        not label_problems,
        "All %d placeholder rows have explicit real-SKU confirmations in %s." % (len(PLACEHOLDER_ROWS), relative(LABELS_PATH))
        if not label_problems else "Edit %s (human input; this script will not create it): %s." % (relative(LABELS_PATH), "; ".join(label_problems)),
    )

    # 5. Resolved #39/#40 duplicate decision ---------------------------------
    decision_problems = []
    if decisions_err:
        decision_problems.append(decisions_err + " A human must create it with a resolved entry for the #39/#40 pair (row numbers 39 and 40, resolved/decision fields and an explicit outcome).")
    else:
        candidates = pair_entries(decisions)
        if not candidates:
            decision_problems.append("no entry covering rows #%d and #%d" % DUPLICATE_PAIR)
        else:
            resolved = [entry for entry in candidates if pair_is_resolved(entry) and pair_decision_text(entry)]
            if not resolved:
                decision_problems.append("the #39/#40 entry exists but is not resolved (set resolved=true and a non-empty decision/outcome)")
    add_check(
        "duplicate_pair_39_40_decision",
        not decision_problems,
        "Resolved #39/#40 decision found in %s." % relative(DECISIONS_PATH)
        if not decision_problems else "Edit %s (human input; this script will not create it): %s." % (relative(DECISIONS_PATH), "; ".join(decision_problems)),
    )

    # 5b. ALL human decisions, not just the #39/#40 pair ----------------------
    queue_problems = []
    if decisions_err:
        queue_problems.append(decisions_err + " A human must resolve every entry before any import/push.")
    else:
        entries = all_decision_entries(decisions)
        if not entries:
            queue_problems.append("no human decision entries found in %s" % relative(DECISIONS_PATH))
        else:
            unresolved = [entry for entry in entries if not decision_is_resolved(entry)]
            if unresolved:
                labels = [clean(entry.get("id")) or ("row #%s" % clean(entry.get("n")) if clean(entry.get("n")) else "<unnamed>") for entry in unresolved]
                queue_problems.append(
                    "%d of %d entries still have a null decision/decided_by/decided_at: %s."
                    % (len(unresolved), len(entries), ", ".join(labels[:20]) + (" ..." if len(labels) > 20 else ""))
                )
    add_check(
        "all_human_decisions_resolved",
        not queue_problems,
        "All %d human decisions are resolved in %s." % (len(all_decision_entries(decisions)), relative(DECISIONS_PATH))
        if not queue_problems else "Edit %s (human input; this script will not create it): %s." % (relative(DECISIONS_PATH), "; ".join(queue_problems)),
    )

    # 6. Relay full-rebuild snapshot safety ----------------------------------
    relay_note = ("PUT /api/agent/catalog deletes only SKUs absent from the pushed snapshot, then upserts "
                  "with pin-preserving semantics and a baseRevision check. Production was confirmed EMPTY by "
                  "direct DB query at verification time, but that is point-in-time only: re-check catalog "
                  "membership immediately before pushing.")
    relay_problems = []
    if snapshot_error:
        relay_problems.append(snapshot_error)
    if scope == "full":
        relay_detail = relay_note + " Full scope pushes the complete 150-row snapshot, so no other rows are at risk. " + snapshot_note + "."
    elif args.relay_empty:
        relay_detail = relay_note + " --relay-empty was supplied: confirm a FRESH direct DB query showed zero rows immediately before this push. " + snapshot_note + "."
    elif snapshot_used:
        relay_detail = relay_note + " Relying on " + snapshot_note + "; confirm the PUT payload is exactly that full snapshot."
    else:
        relay_problems.append("pilot scope needs --relay-empty (after a fresh direct DB check) OR a verified full snapshot via --relay-snapshot [PATH]; default snapshot path is %s." % relative(DEFAULT_SNAPSHOT_PATH))
        relay_detail = relay_note + " " + " ".join(relay_problems)
    add_check("relay_snapshot_safety", not relay_problems, relay_detail if not relay_problems else "Unsafe pilot push -> " + " ".join(relay_problems))

    # 7. Acknowledge the source status-split discrepancy ---------------------
    errata_problems = []
    if errata_err:
        errata_problems.append(errata_err + " A human must create it with an explicit note that the source page-1 split 89/61 is stale and the catalog rows are 95 Verified / 55 Check.")
    else:
        missing_tokens = [token for token in ("95", "55") if not re.search(r"(?<![0-9])%s(?![0-9])" % token, errata_text)]
        if missing_tokens:
            errata_problems.append("%s must explicitly mention %s (the row-level status split); currently missing %s." % (
                relative(ERRATA_PATH), "both 95 and 55", ", ".join(missing_tokens)
            ))
    add_check(
        "status_split_errata_acknowledged",
        not errata_problems,
        "%s acknowledges the 95 Verified / 55 Check row-level split." % relative(ERRATA_PATH)
        if not errata_problems else " ".join(errata_problems),
    )

    # 8. Explicit import/push approval ----------------------------------------
    approval_problems = explicit_approval_problems()
    add_check(
        "explicit_import_push_approval",
        not approval_problems,
        "%s contains exactly '%s'; dry-run planning is allowed without it, but --apply "
        "and any relay push are refused until a human approves." % (relative(APPROVAL_PATH), APPROVAL_TEXT)
        if not approval_problems else "APPROVAL REQUIRED - " + " ".join(approval_problems),
    )

    # Non-blocking warnings --------------------------------------------------
    warnings.append(relay_note)
    if flags_err:
        warnings.append("Cannot count flagged rows: %s." % flags_err)
    elif isinstance(flags, dict):
        checklist = 0
        for key, value in flags.items():
            if isinstance(value, list) and key != "additional_check_status_rows":
                checklist += sum(1 for item in value if isinstance(item, dict) and item.get("decision_needed") is True)
        extra = flags.get("additional_check_status_rows", [])
        extra_count = len(extra) if isinstance(extra, list) else 0
        warnings.append("%d flagged rows (%d checklist rows + %d extra check-carton rows) are still awaiting a physical decision (verify_flags.json). Non-blocking for this gate; resolve before trusting stock status." % (
            checklist + extra_count, checklist, extra_count
        ))
    for data, filename in ((flags, "verify_flags.json"), (totals, "verify_totals.json"), (dedup, "verify_dedup.json")):
        warnings.extend(discrepancy_warnings(data, filename))
    for error, filename in ((flags_err, "verify_flags.json"), (totals_err, "verify_totals.json"), (dedup_err, "verify_dedup.json")):
        if error:
            warnings.append("%s unavailable for discrepancy warnings: %s" % (filename, error))

    hard_blockers = ["%s: %s" % (check["name"], check["detail"]) for check in checks if check["result"] == "FAIL"]
    result = "GO" if not hard_blockers else "NO-GO"
    report = {
        "agent": "L",
        "scope": scope,
        "checks": checks,
        "hard_blockers": hard_blockers,
        "needs_pricing": needs_pricing,
        "warnings": warnings,
        "RESULT": result,
    }
    output_path = STOCK / "import_readiness.json"
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    passed = sum(1 for check in checks if check["result"] == "PASS")
    warned = sum(1 for check in checks if check["result"] == "WARN")
    print("%s scope=%s checks=%d/%d warn=%d blockers=%d needs_pricing=%d warnings=%d report=%s" % (
        result, scope, passed, len(checks), warned, len(hard_blockers), len(needs_pricing),
        len(warnings), relative(output_path)
    ))
    for check in checks:
        if check["result"] in ("FAIL", "WARN"):
            first_line = check["detail"].splitlines()[0]
            print("  %s %s: %s" % (check["result"], check["name"], first_line[:220]))
    return 1 if hard_blockers else 0


if __name__ == "__main__":
    sys.exit(main())
