"""Build a safe, import-ready manifest from the reconciled stock catalog.

This script ONLY prepares data. It never touches the ERP database or the relay.

Rules applied (per owner audit of 2026-11-23 23-55-34.pdf):
  - Hyphen-only / duplicate variants (such as #39 KRG-3730-COMB-NF-G and
    #40 KRG370combi NFG) are merged into 1 canonical SKU and their quantities
    are summed (149 rows, 297 units).
  - The 8 items without a manufacturer code receive stable NO-SKU-NNN internal
    keys with display_sku="NO SKU", no_sku=True, and an urgent update warning.
  - Return items (#6 TCL 50S5K full return, #10 TCL 32S5K 1/4 return) stay
    counted in total qty with is_return=True and a Return label.
  - Unpriced items carry price_status="NO_PRICE" ("No price available").
  - Writes both stock_import/import_manifest.json and shared/catalog_canonical.json.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
IMPORT = ROOT / "stock_import"
SHARED_CATALOG = WORKSPACE_ROOT / "shared" / "catalog_canonical.json"

RETURN_UNITS_BY_ROW = {
    6: 1,
    10: 1,
}

# Explicit hyphen/shorthand duplicate merges verified against handwritten PDF
EXPLICIT_MERGE_INTO = {
    40: 39,  # KRG370combi NFG -> KRG-3730-COMB-NF-G (Krohler 230L No Frost Combi)
}


def norm_sku_key(sku: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", sku.upper())


def load(name: str):
    path = IMPORT / name
    if not path.exists():
        raise SystemExit(f"MISSING: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    catalog = load("canonical_catalog.json")
    resolution = load("resolve_placeholders.json")

    by_number = {int(r["n"]): r for r in catalog}
    substitutes = {int(r["n"]): r for r in resolution.get("rows", [])}
    original_by_number = {
        int(r["n"]): str(r.get("original_sku", "")).strip() for r in substitutes.values()
    }

    # First pass: build raw items and map placeholder NO-SKU rows
    staged_by_n: dict[int, dict] = {}
    for row in sorted(catalog, key=lambda r: int(r["n"])):
        n = int(row["n"])
        item = dict(row)
        item["qty"] = int(item["qty"])
        if n in substitutes:
            expected = original_by_number[n]
            actual = str(row["sku"]).strip()
            if expected.upper() != actual.upper():
                raise SystemExit(
                    f"row {n}: expected placeholder {expected!r}, found {actual!r}"
                )
            item["original_sku"] = actual
            item["sku"] = f"NO-SKU-{n:03d}"
            item["display_sku"] = "NO SKU"
            item["no_sku"] = True
            item["sku_warning"] = "NO SKU — Urgent: scan physical carton and update SKU"
            item["internal_placeholder"] = True
            item["physical_label_check_required"] = True
        else:
            item["display_sku"] = str(item["sku"]).strip()
            item["no_sku"] = False
            item["sku_warning"] = None
            item["internal_placeholder"] = False
            item["physical_label_check_required"] = False

        ret_qty = RETURN_UNITS_BY_ROW.get(n, 0)
        item["is_return"] = ret_qty > 0
        item["return_qty"] = ret_qty
        item["sealed_qty"] = max(0, item["qty"] - ret_qty)
        if ret_qty == 0:
            item["return_label"] = None
        elif ret_qty >= item["qty"]:
            item["return_label"] = "Return"
        else:
            item["return_label"] = f"Return ({ret_qty}/{item['qty']} units)"

        item["merged_from"] = []
        item["sale_price"] = None
        item["pinned_price"] = None
        item["price_status"] = "NO_PRICE"
        item["price_label"] = "No price available"
        item["public_visible"] = (not item["no_sku"]) and (item["sealed_qty"] > 0)
        staged_by_n[n] = item

    # Second pass: merge explicit pairs + any hyphen-only duplicates by incrementing qty
    merged_away: set[int] = set()
    for src_n, dst_n in sorted(EXPLICIT_MERGE_INTO.items()):
        if src_n in staged_by_n and dst_n in staged_by_n:
            src = staged_by_n[src_n]
            dst = staged_by_n[dst_n]
            dst["qty"] += src["qty"]
            dst["sealed_qty"] += src["sealed_qty"]
            dst["return_qty"] += src["return_qty"]
            dst["ledger"] = f"{dst['ledger']} + {src['ledger']}"
            dst["merged_from"].append(src["sku"])
            dst["physical_label_check_required"] = (
                dst["physical_label_check_required"] or src["physical_label_check_required"]
            )
            dst["public_visible"] = (not dst["no_sku"]) and (dst["sealed_qty"] > 0)
            merged_away.add(src_n)

    # Automatic hyphen/space-insensitive merge for any remaining real SKUs
    by_norm: dict[str, dict] = {}
    manifest: list[dict] = []
    for n in sorted(staged_by_n):
        if n in merged_away:
            continue
        item = staged_by_n[n]
        if not item["no_sku"]:
            norm = f"{item['brand'].strip().lower()}::{norm_sku_key(item['sku'])}"
            if norm in by_norm:
                dst = by_norm[norm]
                # Prefer canonical SKU containing hyphens if incoming has hyphens and dst does not
                if "-" in item["sku"] and "-" not in dst["sku"]:
                    dst["merged_from"].append(dst["sku"])
                    dst["sku"] = item["sku"]
                    dst["display_sku"] = item["sku"]
                else:
                    dst["merged_from"].append(item["sku"])
                dst["qty"] += item["qty"]
                dst["sealed_qty"] += item["sealed_qty"]
                dst["return_qty"] += item["return_qty"]
                dst["ledger"] = f"{dst['ledger']} + {item['ledger']}"
                dst["public_visible"] = (not dst["no_sku"]) and (dst["sealed_qty"] > 0)
                continue
            by_norm[norm] = item
        manifest.append(item)

    problems: list[str] = []
    if len(manifest) != 149:
        problems.append(f"expected 149 merged rows, got {len(manifest)}")
    expected_ns = [i for i in range(1, 151) if i not in merged_away]
    if sorted(int(r["n"]) for r in manifest) != expected_ns:
        problems.append("row numbering mismatch after #39/#40 merge")
    units = sum(int(r["qty"]) for r in manifest)
    if units != 297:
        problems.append(f"expected 297 units, got {units}")

    counts = Counter(str(r["sku"]).strip().upper() for r in manifest)
    collisions = {s: c for s, c in counts.items() if c > 1}
    if collisions:
        problems.append(f"duplicate effective SKUs: {collisions}")

    altered = [
        n for n in substitutes
        if str(by_number[n]["sku"]).strip().upper()
        != str(original_by_number[n]).strip().upper()
    ]
    if altered:
        problems.append(f"unexpected source mutation rows: {altered}")

    for check in resolution.get("checks", []):
        if check.get("result") != "PASS":
            problems.append(f"placeholder check {check.get('name')}: {check.get('result')}")

    out = {
        "rows": len(manifest),
        "units": units,
        "internal_placeholders": sum(1 for r in manifest if r["internal_placeholder"]),
        "no_sku_count": sum(1 for r in manifest if r["no_sku"]),
        "return_rows": sum(1 for r in manifest if r["is_return"]),
        "return_units": sum(int(r["return_qty"]) for r in manifest),
        "merged_pairs": [{"into_n": dst, "from_n": src} for src, dst in sorted(EXPLICIT_MERGE_INTO.items())],
        "products": manifest,
        "problems": problems,
        "RESULT": "READY FOR PILOT REVIEW" if not problems else "DO NOT IMPORT",
    }
    target = IMPORT / "import_manifest.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    SHARED_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    SHARED_CATALOG.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"rows={len(manifest)} units={units} no_sku={out['no_sku_count']} "
        f"returns={out['return_rows']}({out['return_units']}u)"
    )
    print(f"problems={len(problems)} RESULT={out['RESULT']}")
    for p in problems:
        print("PROBLEM:", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
