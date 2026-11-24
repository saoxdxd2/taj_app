"""Merge the parallel register extractions and cross-check the independent audits.

Strict where it matters (row counts, quantities, duplicate SKUs, unresolved
extractor notes) and explicit about source-document discrepancies that need a
human decision. Writes a canonical catalog plus a reconciliation report.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT = ROOT / "stock_import"

REQUIRED_FIELDS = ("n", "category", "brand", "sku", "spec", "qty", "status", "ledger", "page")
UNCERTAINTY_KEYWORDS = (
    "uncertain", "could not determine", "cannot determine", "not sure",
    "unsure", "i guess", "best guess", "unable to",
)
# Only an explicit "P4 (×3)" style marker allocates a split count. Digits
# inside ordinary codes such as "P4 (138 cm)" or "P8 (43LM63)" are NOT counts.
LEDGER_RE = re.compile(r"(?<![A-Za-z0-9])P([1-8])(?:\s*\(\s*[×xX]\s*(\d+))?")


def load(name: str):
    path = IMPORT / name
    if not path.exists():
        raise SystemExit(f"MISSING: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def allocate_ledger_units(ledger: str, qty: int) -> dict[str, int]:
    """Allocate a row's qty across the ledger sheets named in its source cell.

    Handles 'P4 (×2) + P7 (×1)', plain 'P8', and wrapped codes like
    'P2 (FIF463)' where no split count is present.
    """
    # A sheet token must start the cell or follow '+' / whitespace. Codes such
    # as "P2 (P70H20L-QK)" contain letter-digit sequences that look like sheet
    # tokens but are model shorthands, not ledger references.
    matches = [
        m for m in LEDGER_RE.finditer(ledger)
        if m.start() == 0 or ledger[m.start() - 1] in " +"
    ]
    if not matches:
        return {}
    explicit = [(m.group(1), int(m.group(2))) for m in matches if m.group(2)]
    if explicit:
        out: dict[str, int] = defaultdict(int)
        for sheet, count in explicit:
            out[f"P{sheet}"] += count
        return dict(out)
    sheets = [f"P{m.group(1)}" for m in matches]
    if len(sheets) == 1:
        return {sheets[0]: qty}
    # Multiple sheets with no explicit split: the source does not say how to
    # divide, so do not guess. Attribute nothing and record the ambiguity.
    return {}


def main() -> int:
    blockers: list[str] = []
    source_discrepancies: list[str] = []
    audit_notes: list[str] = []
    documented_resolutions: list[str] = []
    records: list[dict] = []

    for letter in "ABCDE":
        payload = load(f"extract_{letter}.json")
        rows = payload.get("records", [])
        print(f"extract_{letter}: {len(rows)} rows, qty_sum={sum(int(r['qty']) for r in rows)}")
        for row in rows:
            missing = [f for f in REQUIRED_FIELDS if f not in row]
            if missing:
                blockers.append(f"row {row.get('n')}: missing fields {missing}")
            note = str(row.get("notes") or "").strip()
            if note:
                message = f"row {row.get('n')}: {note}"
                if any(word in note.lower() for word in UNCERTAINTY_KEYWORDS):
                    blockers.append(f"UNRESOLVED EXTRACTOR NOTE - {message}")
                else:
                    documented_resolutions.append(message)
            records.append(row)

    records.sort(key=lambda r: int(r["n"]))
    numbers = [int(r["n"]) for r in records]
    if len(records) != 150:
        blockers.append(f"expected 150 rows, got {len(records)}")
    expected_numbers = list(range(1, 151))
    if numbers != expected_numbers:
        gaps = sorted(set(expected_numbers) - set(numbers))
        dups = [n for n, c in Counter(numbers).items() if c > 1]
        blockers.append(f"numbering mismatch: gaps={gaps} duplicates={dups}")

    qty_sum = sum(int(r["qty"]) for r in records)
    if qty_sum != 297:
        blockers.append(f"expected 297 units, got {qty_sum}")

    sku_counts = Counter(str(r["sku"]).strip() for r in records)
    placeholder_rows = [
        {"n": r["n"], "sku": r["sku"], "brand": r["brand"], "qty": r["qty"], "spec": r["spec"]}
        for r in records
        if str(r["sku"]).strip().upper() in {"[NO CODE]", "NO CODE", "N/A", "UNKNOWN", "-"}
    ]
    real_sku_counts = Counter(
        str(r["sku"]).strip() for r in records
        if str(r["sku"]).strip().upper() not in {"[NO CODE]", "NO CODE", "N/A", "UNKNOWN", "-"}
    )
    dup_skus = {s: c for s, c in real_sku_counts.items() if c > 1}
    if placeholder_rows:
        blockers.append(
            f"{len(placeholder_rows)} rows have placeholder SKUs and would collapse on import: "
            f"{[r['n'] for r in placeholder_rows]}"
        )
    if dup_skus:
        blockers.append(f"duplicate real SKU values: {dup_skus}")

    by_category: dict[str, list[int]] = defaultdict(list)
    by_ledger: dict[str, int] = defaultdict(int)
    unallocated = []
    status_counts: Counter = Counter()
    for r in records:
        by_category[r["category"]].append(int(r["qty"]))
        status_counts[r["status"]] += 1
        allocated = allocate_ledger_units(r["ledger"], int(r["qty"]))
        if not allocated and re.search(r"P[1-8]", r["ledger"]):
            unallocated.append(r["n"])
        for sheet, units in allocated.items():
            by_ledger[sheet] += units

    totals = load("verify_totals.json")
    for check in totals.get("checks", []):
        if check.get("result") == "PASS":
            continue
        message = f"{check.get('name')}: {check.get('note')}"
        if "split" in check.get("name", "").lower() or "status" in check.get("name", "").lower():
            source_discrepancies.append(f"SOURCE DOCUMENT - {message}")
        else:
            blockers.append(f"TOTALS AUDIT FAIL - {message}")
    derived = totals.get("derived_from_text", {})
    if derived.get("row_count") not in (None, 150):
        blockers.append(f"totals audit derived row_count={derived.get('row_count')}")
    if derived.get("qty_sum") not in (None, 297):
        blockers.append(f"totals audit derived qty_sum={derived.get('qty_sum')}")

    dedup = load("verify_dedup.json")
    purged = [str(s).strip() for s in dedup.get("purged_skus", [])]
    retained = {s: sku_counts.get(s, 0) for s in purged}
    wrong_retention = {s: c for s, c in retained.items() if c != 1}
    if len(purged) != 14:
        blockers.append(f"dedup audit listed {len(purged)} purged SKUs, expected 14")
    if wrong_retention:
        blockers.append(f"purged SKUs not retained exactly once: {wrong_retention}")
    if dedup.get("source_codes_still_present"):
        blockers.append(f"pre-merge source codes still present: {dedup['source_codes_still_present']}")
    if dedup.get("duplicate_sku_values") and set(dedup["duplicate_sku_values"]) - {"[No code]"}:
        blockers.append(f"dedup audit duplicates: {dedup['duplicate_sku_values']}")
    if dedup.get("numbering", {}).get("contiguous") is False:
        blockers.append(f"dedup audit numbering: {dedup['numbering']}")
    for extra in dedup.get("discrepancies", []):
        audit_notes.append(f"dedup: {extra}")

    flags = load("verify_flags.json")
    flagged_rows: list[dict] = []
    for group in ("overwritten_qty", "returns", "missing_model_or_brand", "possible_duplicate_pair"):
        flagged_rows.extend(flags.get(group, []))
    by_number = {int(r["n"]): r for r in records}
    for item in flagged_rows:
        n = int(item.get("n", 0))
        row = by_number.get(n)
        if row is None:
            blockers.append(f"flag audit references missing row #{n}")
            continue
        for field in ("sku", "brand", "qty", "status"):
            if field in item and str(item[field]).strip() != str(row[field]).strip():
                blockers.append(f"flag #{n} {field} mismatch: audit={item[field]!r} extract={row[field]!r}")
    for extra in flags.get("discrepancies", []):
        audit_notes.append(f"flags: {extra}")

    canonical = [
        {
            "n": r["n"], "category": r["category"], "brand": r["brand"],
            "sku": r["sku"], "name": r["spec"], "qty": int(r["qty"]),
            "status": r["status"], "ledger": r["ledger"], "source_page": r["page"],
        }
        for r in records
    ]
    (IMPORT / "canonical_catalog.json").write_text(
        json.dumps(canonical, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "rows": len(records),
        "units": qty_sum,
        "status_counts": dict(status_counts),
        "category_counts": {k: len(v) for k, v in by_category.items()},
        "category_units": {k: sum(v) for k, v in by_category.items()},
        "ledger_units_allocated": dict(by_ledger),
        "ledger_rows_not_allocated": unallocated,
        "duplicate_real_skus": dup_skus,
        "placeholder_sku_rows": placeholder_rows,
        "purged_skus_retained_once": retained,
        "flagged_rows_count": len(flagged_rows),
        "documented_resolutions_count": len(documented_resolutions),
        "documented_resolutions": documented_resolutions,
        "source_document_discrepancies": source_discrepancies,
        "audit_notes": audit_notes,
        "blockers": blockers,
        "RESULT": "PASS" if not blockers else "DO NOT IMPORT - BLOCKERS PRESENT",
    }
    (IMPORT / "reconciliation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"rows={len(records)} units={qty_sum} statuses={dict(status_counts)}")
    print(f"blockers={len(blockers)} source_discrepancies={len(source_discrepancies)}")
    for b in blockers:
        print("BLOCKER:", b)
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
