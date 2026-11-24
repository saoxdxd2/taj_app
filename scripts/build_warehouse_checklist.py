"""Render the audited flag data into a human-readable warehouse checklist."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT = ROOT / "stock_import"

GROUPS = (
    ("Overwritten quantities", "overwritten_qty"),
    ("Customer returns", "returns"),
    ("Missing model code or brand", "missing_model_or_brand"),
    ("Possible duplicate pair", "possible_duplicate_pair"),
    ("Check-carton rows not on the page-11 checklist", "additional_check_status_rows"),
)


def fmt(item: dict) -> str:
    lines = [
        f"- **#{item['n']} — {item['brand']} — `{item['sku']}` — qty {item['qty']} — {item['status']}**",
        f"  - Ledger source: `{item['ledger']}` | {item.get('page', '?')}",
        f"  - Decision: {item.get('decision_reason', '')}",
    ]
    if item.get("excluded_qty") is not None:
        lines.append(f"  - Exclude qty: {item['excluded_qty']} ({item.get('exclusion_scope', '')})")
    if item.get("merge_action_if_same_barcode"):
        lines.append(f"  - If barcodes match: {item['merge_action_if_same_barcode']}")
    return "\n".join(lines)


def main() -> int:
    flags = json.loads((IMPORT / "verify_flags.json").read_text(encoding="utf-8"))
    placeholders = json.loads((IMPORT / "resolve_placeholders.json").read_text(encoding="utf-8"))
    manifest = json.loads((IMPORT / "import_manifest.json").read_text(encoding="utf-8"))

    out = [
        "# Warehouse verification checklist — audited stock register",
        "",
        "Source: `Electronics Stock Register.pdf` (audited edition, 150 SKUs / 297 units).",
        "Do **not** push the full 150-row import until every item below is resolved.",
        "",
        f"Catalog status counts from the 150 table rows: "
        f"**{flags['status_counts']['Verified']} Verified**, "
        f"**{flags['status_counts']['Check carton']} Check carton**, "
        f"**{flags['status_counts']['Check box']} Check box**.",
        "The page-1 printed split (89 / 61) is stale — the table rows are authoritative.",
        "",
    ]
    for title, key in GROUPS:
        items = flags.get(key, [])
        out += [f"## {title} ({len(items)})", ""]
        out += [fmt(i) for i in items]
        out.append("")

    out += [
        "## Internal placeholder SKUs — physical label/barcode required (8)",
        "",
        "These eight rows had no model code on the handwritten sheet. They have been given "
        "**internal** `PH-...` codes solely so the import is lossless. These are NOT "
        "manufacturer model numbers. Scan the carton and replace each with the real SKU "
        "before treating the product as sellable.",
        "",
    ]
    for row in placeholders.get("rows", []):
        out.append(
            f"- **#{row['n']}** — `{row['original_sku']}` → **`{row['proposed_internal_sku']}`** "
            f"— physical label check required: yes"
        )
    out += [
        "",
        "## Source-document discrepancies (no data change made)",
        "",
    ]
    out += [f"- {d}" for d in flags.get("discrepancies", [])]
    out += [""]

    target = IMPORT / "WAREHOUSE_CHECKLIST.md"
    target.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {target} ({len(out)} lines); manifest rows={manifest['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
