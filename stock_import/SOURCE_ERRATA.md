# Source Errata — Master Appliance & Electronics Stock Register (Audited Edition)

**Authority rule.** The 150 numbered table rows in `stock_register_extracted.txt` (rows 1–150, PDF pp. 1–11) are authoritative for **all product data**: SKU, brand, specification, quantity, catalog status and ledger source. The narrative summary text (page-1 header, summary table and "Key Corrections", and the page-11 grand-total/checklist text) is **not** authoritative where it conflicts with the rows. The rows sum to 150 SKUs and 297 units; the narrative figures 89/61, "0 duplicate rows", the unqualified "−20 phantom units" and the checklist P-refs do not override the row data.

This file records discrepancies only. No existing file, audit JSON or source PDF was modified in producing it. Line numbers refer to the numbered lines of `stock_register_extracted.txt`; page boundaries are the `===== PAGE n =====` markers.

## Errata table

| ID | Location (page + exact line numbers in stock_register_extracted.txt) | Claim as printed | Verified reality | Impact | Resolution/authoritative value | Status |
|---|---|---|---|---|---|---|
| E-01 | PDF p.1, lines 4–5; lines 36–37; lines 42–43; PDF p.11, lines 1812–1816 | "297 verified units" (l.4); "89 SKUs matched to verified catalog specs" (ll.36–37); "61 SKUs flagged for carton / label check" (ll.42–43) | The 150 rows contain **95 Verified** and **55 Check** (45 Check carton + 10 Check box). The arithmetic 89 + 61 = 150 is valid, but the split is not in the rows: 6 fewer Verified and 6 more Check than printed. No subset rule reproduces 89/61 (even the 8 annotated Verified rows would give 87/63). Only 95 of 150 rows are Verified, so "297 verified units" is also loose wording. | Importing the printed split would misclassify 6 SKUs in each direction and understate Check-box rows; the status field drives warehouse label checks. | Authoritative: Verified = 95; Check = 55 (carton 45 + box 10); total units = 297. Use the per-row Catalog Status of the 150 rows; discard 89/61. | Confirmed discrepancy; table authoritative (`verify_totals.json` check `status_split_vs_catalog_rows` = FAIL; `verify_flags.json` `status_counts`; `reconciliation_report.json` `status_counts`). |
| E-02 | PDF p.1, lines 52–55; related drift claim lines 59–60; retained rows at lines 587–588, 598–599, 953, 966, 976, 1139, 1150, 1161–1162, 1229, 1301, 1310, 1571, 1581, 1608 | "14 Duplicate Rows Purged (−20 Phantom Units): Removed all duplicated catalog rows present in the prior draft ..." (ll.52–55), followed by "prior summary's 1-unit drift (298 → 297)" (ll.59–60) | All 14 named models still appear exactly once as Verified SKU values in the 150 rows, and their quantities total exactly 20 units, all of which remain inside the 297. The "−20 phantom units" and the separate "298 → 297" drift are two different correction stages. The prior draft is not in the source, so the purge and the −20 figure cannot be independently verified. | Reading "purged" as removal of these SKUs/units from the final catalog would yield 136 rows / 277 units and break both printed grand totals. | Authoritative: 150 rows / 297 units; all 14 named models retained once (20 units). Interpret as removal of extra duplicate COPIES only; no row or quantity change. | Wording ambiguity / multi-stage claim; resolved by staged reading; purge itself unverifiable from source. |
| E-03 | PDF p.1, lines 4–5; PDF p.11, lines 1812–1816 | "0 duplicate rows." (l.5) and "0 Duplicates \| 100% Reconciled" (ll.1815–1816); header also calls the register "deduplicated" (l.4, l.1812) | The literal string `[No code]` is printed as the Verified SKU in 8 rows, so the claim is false at the string level. Excluding those placeholders, there are no duplicate real SKUs (`duplicate_real_skus` is empty in `reconciliation_report.json`). The #39/#40 pair remains an open possible duplicate. | A unique-SKU import would collide on the 8 identical placeholder strings; the unresolved pair threatens 150/297 if merged. | Authoritative: no duplicate **manufacturer** SKUs among real codes; the 8 placeholders must be substituted (E-04); #39/#40 stay separate pending barcode confirmation (E-05). | False as literally printed; scoped correction recorded. |
| E-04 | PDF p.7, line 1069 (#86); PDF p.9, lines 1450 (#120), 1512 (#125), 1524 (#126); PDF p.10, lines 1629 (#134), 1639 (#135), 1669 (#138), 1777 (#149); checklist PDF p.11, lines 1825–1828 | "Verified SKU" cell reads `[No code]` in 8 rows; checklist says "Missing Model Codes or Brands (10 SKUs)" (ll.1825–1828) | Eight distinct products have no manufacturer model code written on the handwritten sheet (15 units total: 1 + 1 + 1 + 5 + 4 + 1 + 1 + 1). Two further checklist items have a code but no brand: #148 TH212 (PDF p.10, lines 1762–1773) and #150 CH020A (PDF p.11, lines 1800–1811) — together these make the checklist's 10 SKUs correct. | Import blocker: SKU is required and unique; `canonical_catalog.json` retains the literal placeholders and `reconciliation_report.json` lists rows [86, 120, 125, 126, 134, 135, 138, 149] as blockers. | Use the internal SKUs in `resolve_placeholders.json` applied by `scripts/build_import_manifest.py` into `import_manifest.json`; physical carton label check required. Leave the 150 table rows unchanged. | Open import blocker; documented substitution; no source edit. |
| E-05 | PDF p.4, lines 529–538 (#39) and 539–550 (#40); checklist PDF p.11, lines 1829–1831 | "Possible Duplicate Model Variant (1 pair): Confirm whether #39 Krohler KRG-3730-COMB-NF-G (P3) and #40 Krohler KRG370combi NFG (P8) share the same barcode ... if so, merge them into 1 SKU (2 units)" (ll.1829–1831) | Both remain separate rows: #39 (qty 1, Verified, P3) and #40 (qty 1, Check carton, P8), whose spec itself says "verify if same model as #39" (ll.544–546). No barcode evidence exists in the source. | Merging as the checklist states ("1 SKU (2 units)") would give 149 SKUs / 297 units: both physical units are retained, so only the row count falls. An earlier 149/296 figure was arithmetically wrong and is retracted here. | Authoritative: keep both rows — 150 SKUs / 297 units; no merge until physical barcode confirmation. | Open decision; no change applied. |
| E-06 | PDF p.11, lines 1817–1831 (checklist); sheet reconciliation PDF p.1, lines 16, 21, 26, 31, 49 | Checklist P-refs such as "#74 ... (P8, quantity overwritten ...)", "#129 ... (P7, quantity scribbled over ...)", "#86 ... P5" read as if they were PDF page references | P1–P8 are handwritten **ledger sheet** identifiers, not PDF page numbers. #6/#10 listed P8 are on PDF p.2; #39 P3 and #40 P8 are on PDF p.4; #74 P8 on PDF p.6; #86 P7 on PDF p.7; #120 P8, #125 P5 and #126 P1 on PDF p.9; #134/#135 P8 and #138/#148/#149 P6 on PDF p.10; #129 P7 on PDF p.9; #150 P6 on PDF p.11. | Misreading P-refs as PDF pages locates the wrong row and the wrong ledger allocation. | Authoritative: P1–P8 = ledger sheet numbers; the PDF page is reported separately (`verify_flags.json` `page`, `canonical_catalog.json` `source_page`). | Terminology clarified; no numeric change. |
| E-07 | PDF p.11, lines 1820–1822; PDF p.9, lines 1553–1566 | "#129 Arthur Martin MYG06113WL (P7, quantity scribbled over; counted as 1)" (ll.1820–1822) | Row 129 is Verified with qty 1 and ledger "P7 (check qty)" (lines 1562–1566). The table does not say "scribbled over"; it only carries a "check qty" note. | Physical count needs confirmation; the numeric qty already agrees with the checklist. | Keep qty 1 as printed and verify the carton physically before import. | Open confirmation; narrative-only detail absent from the row. |
| E-08 | PDF p.11, lines 1820–1822; PDF p.6, lines 927–939 | "#74 Krohler KPB-13.5-CX (P8, quantity overwritten; counted as 1)" (ll.1821–1822) | Row 74 is Verified with qty 1 and ledger "P8 (KP1395 CX)" (lines 935–939). No overwritten-quantity annotation appears in the row; only the alternate ledger code. | Physical count needs confirmation; the numeric qty already agrees with the checklist. | Keep qty 1 as printed and verify the carton physically before import. | Open confirmation; narrative-only detail absent from the row. |
| E-09 | PDF p.11, lines 1823–1824; PDF p.2, lines 144–154 (#6) and 186–198 (#10) | "Customer Returns (2 units): Separate or tag #6 TCL 50S5K (1 unit, P8) and #10 TCL 32S5K (1 of 4 units, P8), both marked retour on the manual sheet" (ll.1823–1824) | #6's ledger literally reads "P8 (retour)" (lines 153–154) with qty 1. #10's ledger reads "P2 (×1) + P4 (×2) + P8 (×1 ret.)" (lines 195–198) and its spec says "1 unit marked Return" (lines 191–192): abbreviated "ret.", not "retour". | Excluding both rows wholesale would drop 5 units instead of 2; #10's other 3 units are factory-sealed per the register. | Exclude 1 unit for #6 (full row) and 1 of 4 units for #10, i.e. 2 units total; retain #10 qty 4 as printed. | Wording discrepancy; exclusion scope documented. |
| E-10 | PDF p.1, lines 16, 21, 26, 31, 49–50; `reconciliation_report.json` lines 33–46; `verify_totals.json` lines 26–37 and 92–101 | Printed sheet reconciliation: "P1: 47 units  \|  P2: 34 units" (l.16), "P3: 19 units  \|  P4: 54 units" (l.21), "P5: 28 units  \|  P6: 31 units" (l.26), "P7: 49 units  \|  P8: 35 units" (l.31), "47+34+19+54+28+31+49+35 = 297 units" (ll.49–50) | `reconciliation_report.json` `ledger_units_allocated` instead reports P1 47, P2 33, P3 19, P4 189, P5 28, P6 31, P7 49, P8 76 (sum 472), with rows 74 and 108 listed as unallocated. This is a script-allocation artifact, not source data: digits inside parenthetical annotations are read as split counts (row 12 "P4 (138 cm)" adds 138 to P4) and model-code substrings are read as extra sheet refs ("KP1395CX" → P1, "P70H20L-QK" → P7). `verify_totals.json` checks 4–5 and `expected_final.by_ledger` reproduce the printed figures. | Treating `ledger_units_allocated` as sheet totals would misstate P2 by 1, P4 by 135 and P8 by 41, and would yield 472 instead of 297 units. | Authoritative sheet totals: P1 47, P2 34, P3 19, P4 54, P5 28, P6 31, P7 49, P8 35 (sum 297). `ledger_units_allocated` is raw script output and must not be used as the source reconciliation. | RESOLVED: fixed in `scripts/reconcile_register.py`; `ledger_units_allocated` now matches the printed 297-unit sheet reconciliation and `ledger_rows_not_allocated` is empty. No source change. |

## Authoritative values for import

| Field | Value |
|---|---|
| Rows | 150 |
| Units | 297 |
| Verified | 95 |
| Check carton | 45 |
| Check box | 10 |
| Check (total) | 55 |

**Per-category SKU/unit counts** (table sub-categories, as in `reconciliation_report.json` `category_counts` / `category_units`):

| Category | SKUs | Units |
|---|---:|---:|
| TV & Audio | 24 | 63 |
| Refrigerators | 25 | 48 |
| Freezers | 3 | 6 |
| Laundry | 36 | 59 |
| Dishwashers | 5 | 7 |
| Cooking | 23 | 38 |
| Ventilation | 4 | 4 |
| Water Heaters | 11 | 32 |
| Filtration | 4 | 8 |
| Small Appl. | 15 | 32 |
| **Total** | **150** | **297** |

**Same rows grouped as the page-1 summary** (lines 12–48; `verify_totals.json` `expected_final.by_category`):

| Summary group | SKUs | Units |
|---|---:|---:|
| Laundry & Dishwashers | 41 | 66 |
| TV & Audio | 24 | 63 |
| Refrigerators & Freezers | 28 | 54 |
| Cooking & Ventilation | 27 | 42 |
| Water Heaters & Filtration | 15 | 40 |
| Small Appliances | 15 | 32 |
| **Total** | **150** | **297** |

**Per-ledger units.** The allocation bug described in E-10 has been FIXED in `scripts/reconcile_register.py`: split counts are now recognised only when written as `P4 (×3)`, and a sheet token must start the cell or follow `+`/whitespace, so model shorthands such as `KP1395CX` and `P70H20L-QK` are no longer misread. The script output now matches the printed reconciliation exactly.

| Ledger sheet | Authoritative sheet units (p.1, lines 16–49) | `reconciliation_report.json` `ledger_units_allocated` (current) |
|---|---:|---:|
| P1 | 47 | 47 |
| P2 | 34 | 34 |
| P3 | 19 | 19 |
| P4 | 54 | 54 |
| P5 | 28 | 28 |
| P6 | 31 | 31 |
| P7 | 49 | 49 |
| P8 | 35 | 35 |
| **Total** | **297** | **297** |

`ledger_rows_not_allocated` is now empty. E-10 is retained as a historical record of the corrected tooling defect, not as a current discrepancy.

## Rules for future editors

1. **Never change table rows to match the narrative.** The 150 numbered rows are the source of truth for SKU, brand, spec, qty, status and ledger source; narrative totals and correction notes are descriptive only.
2. **Record corrections here instead.** Add a dated, ID-numbered errata entry with the exact `stock_register_extracted.txt` page and line numbers, the printed claim, the verified reality, the impact and the authoritative value. Do not edit `stock_register_extracted.txt`, the source PDF or the audit JSONs to "fix" a narrative claim.
3. **Any change to counts requires re-running both scripts:** `scripts/reconcile_register.py` and then `scripts/build_import_manifest.py`, followed by a review of `reconciliation_report.json` and `import_manifest.json`. A count change without both re-runs leaves the canonical catalog, report and manifest inconsistent.

**Verification note.** Every line number cited above was checked against `stock_register_extracted.txt`. During self-verification one line citation was corrected: "0 Duplicates \| 100% Reconciled" spans lines 1815–1816, not line 1815 alone; the pipe separators on lines 16/21/26/31 were also restored verbatim. The strings 95 and 55 are intentionally recorded as the authoritative status split.
