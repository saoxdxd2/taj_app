"""Build a safe, import-ready manifest from the reconciled stock catalog.

This script ONLY prepares data. It never touches the ERP database or the relay.

It applies the reviewed internal placeholder SKUs for rows whose manufacturer
code was never written on the source ledger, then enforces the invariants that
must hold before any push:
  - 150 rows, 297 units
  - row numbers 1..150 contiguous
  - every effective SKU unique (case-insensitive)
  - no real manufacturer SKU altered
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT = ROOT / "stock_import"


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

    manifest = []
    for row in sorted(catalog, key=lambda r: int(r["n"])):
        n = int(row["n"])
        item = dict(row)
        if n in substitutes:
            expected = original_by_number[n]
            actual = str(row["sku"]).strip()
            if expected.upper() != actual.upper():
                raise SystemExit(
                    f"row {n}: expected placeholder {expected!r}, found {actual!r}"
                )
            item["original_sku"] = actual
            item["sku"] = substitutes[n]["proposed_internal_sku"]
            item["internal_placeholder"] = True
            item["physical_label_check_required"] = bool(
                substitutes[n].get("physical_label_check_required", True)
            )
        else:
            item["internal_placeholder"] = False
            item["physical_label_check_required"] = False
        manifest.append(item)

    problems: list[str] = []
    if len(manifest) != 150:
        problems.append(f"expected 150 rows, got {len(manifest)}")
    if sorted(int(r["n"]) for r in manifest) != list(range(1, 151)):
        problems.append("row numbering is not contiguous 1..150")
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
        "products": manifest,
        "problems": problems,
        "RESULT": "READY FOR PILOT REVIEW" if not problems else "DO NOT IMPORT",
    }
    target = IMPORT / "import_manifest.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"rows={len(manifest)} units={units} placeholders={out['internal_placeholders']}")
    print(f"problems={len(problems)} RESULT={out['RESULT']}")
    for p in problems:
        print("PROBLEM:", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
