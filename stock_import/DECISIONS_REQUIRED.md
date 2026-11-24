# Decisions required before import

**Status: DO NOT IMPORT.** This queue has **24 unresolved decisions**, all left with `decision`, `decided_by` and `decided_at` set to `null`. Fill `stock_import/decision_queue.json` and `stock_import/label_confirmations.json` before any push.

Note: `page` below is the PDF page; ledger sheet IDs (P1..P8) are in `ledger`.

## 1. Possible duplicate pair - 1 decision (DQ-001), rows #39 / #40
**What to do:** Compare the two carton barcodes (#39 `KRG-3730-COMB-NF-G`, P3, Verified; #40 `KRG370combi NFG`, P8, Check carton, both PDF p.4). Choose: keep separate (150/297), merge into 1 SKU with 2 units (149/297), or defer. Recommended: defer until the barcodes are physically compared.
**If deferred:** Both rows stay excluded from the import; row/unit totals stay 150/297.
**Arithmetic note:** the checklist explicitly says "merge them into 1 SKU (2 units)", so merging gives **149 rows / 297 units** — both physical units are kept and only the row count falls. An earlier 149/296 figure was wrong and has been retracted from all artifacts.

## 2. Internal placeholder SKUs - 8 decisions (DQ-002 - DQ-009), rows #86, #120, #125, #126, #134, #135, #138, #149
**What to do:** For each row, scan the carton barcode and write the real manufacturer SKU into `label_confirmations.json` (`confirmed_real_sku`, `confirmed_by`, `confirmed_at`, `barcode_photo_ref`) and record the same answer in the queue. The `PH-...` codes are internal only, never sellable. Rows: #86 Tatch -> PH-086-LAU-TAT-P5; #120 General -> PH-120-VEN-GEN-P8; #125 Junkers -> PH-125-WAT-JUN-P5; #126 Chaffoteaux -> PH-126-WAT-CHA-P1; #134 Eco Aqua -> PH-134-FIL-ECO-P8; #135 Tatch -> PH-135-FIL-TAT-P8; #138 Severin -> PH-138-SMA-SEV-P6; #149 Taurus -> PH-149-SMA-TAU-P6.
**If deferred:** The rows cannot be pushed sellably; all 8 remain blockers (they would collapse on import if sent as-is).

## 3. Returns - 2 decisions (DQ-010, DQ-011), rows #6 and #10
**What to do:** #6 (`50S5K`, ledger `P8 (retour)`): tag/exclude the full qty 1. #10 (`32S5K`, ledger `P2 (×1) + P4 (×2) + P8 (×1 ret.)`): identify and exclude only 1 of the 4 units, keep the other 3 sealed.
**If deferred:** Keep both rows out of the import; do not list the returned cartons as factory-sealed.

## 4. Overwritten quantities - 2 decisions (DQ-012, DQ-013), rows #129 and #74
**What to do:** Physically recount and confirm qty 1 for #129 (`MYG06113WL`, `P7 (check qty)`) and #74 (`KPB-13.5-CX`, ledger `P8 (KP1395 CX)`); the table value is 1 for both.
**If deferred:** Neither row may be imported with an unverified quantity.

## 5. Missing model or brand - 10 decisions (DQ-014 - DQ-023), rows 86, 120, 125, 126, 134, 135, 138, 148, 149, 150
**What to do:** Rows #86, #120, #125, #126, #134, #135, #138, #149 are the same 8 physical items as group 2 - resolve each once, then record the answer in both entries. #148 (`TH212`) and #150 (`CH020A`) have model codes but no brand: confirm the brand from the carton (correct the SKU too if the carton disagrees).
**If deferred:** Those rows remain unchecked for model/brand and the import stays blocked.

## 6. Extra check-carton rows - 1 bulk-confirm decision (DQ-024), exactly 44 rows
**What to do:** Physically verify that each carton label/SKU/brand/qty matches its row, then bulk-confirm; record any mismatch before marking. Rows covered (exact set): 2, 3, 5, 8, 29, 44, 46, 48, 51, 52, 63, 64, 65, 66, 71, 73, 79, 80, 81, 82, 83, 85, 87, 88, 93, 96, 98, 104, 105, 107, 110, 113, 115, 119, 127, 130, 133, 136, 139, 141, 142, 144, 145, 147.
**If deferred:** All 44 rows stay unverified and the full import stays blocked.

## After decisions
Re-check that `unresolved_count` equals the number of null decisions before preparing any import/push payload. Prices are no longer a hard blocker: missing/zero prices are NEEDS PRICING warnings and rows are staged DRAFT at `sale_price=0.00` with no pin (see `PRICE_GATE.md`). If in doubt, defer: every null decision still blocks the import.
