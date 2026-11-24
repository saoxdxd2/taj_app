# Warehouse verification checklist — audited stock register

Source: `Electronics Stock Register.pdf` (audited edition, 150 SKUs / 297 units).
Do **not** push the full 150-row import until every item below is resolved.

Catalog status counts from the 150 table rows: **95 Verified**, **45 Check carton**, **10 Check box**.
The page-1 printed split (89 / 61) is stale — the table rows are authoritative.

## Overwritten quantities (2)

- **#129 — Arthur Martin — `MYG06113WL` — qty 1 — Verified**
  - Ledger source: `P7 (check qty)` | PDF p.9
  - Decision: Confirm the physically counted quantity is 1: the checklist says the handwritten quantity was scribbled over. Table row is Verified with ledger note 'P7 (check qty)'.
- **#74 — Krohler — `KPB-13.5-CX` — qty 1 — Verified**
  - Ledger source: `P8 (KP1395 CX)` | PDF p.6
  - Decision: Confirm the physically counted quantity is 1: the checklist says the handwritten quantity was overwritten. Table row is Verified and carries no overwrite note, only the alternate ledger code 'P8 (KP1395 CX)'.

## Customer returns (2)

- **#6 — TCL — `50S5K` — qty 1 — Verified**
  - Ledger source: `P8 (retour)` | PDF p.2
  - Decision: Segregate/tag the returned carton so it is not listed as factory-sealed. The ledger literally reads 'P8 (retour)' and the whole row is qty 1, so the document supports excluding the full qty (1 unit).
  - Exclude qty: 1 (full row qty 1 (the only unit is the retour))
- **#10 — TCL — `32S5K` — qty 4 — Verified**
  - Ledger source: `P2 (×1) + P4 (×2) + P8 (×1 ret.)` | PDF p.2
  - Decision: Segregate/tag 1 returned unit of the 4. The checklist says '1 of 4 units' and the ledger reads 'P8 (×1 ret.)', so exclude only 1 unit; the other 3 remain factory-sealed per the document.
  - Exclude qty: 1 (only 1 of 4 units (P8 ×1 ret.); do not exclude the other 3)

## Missing model code or brand (10)

- **#86 — Tatch — `[No code]` — qty 1 — Check box**
  - Ledger source: `P5` | PDF p.7
  - Decision: Scan the carton barcode to identify the missing model code before import (10 kg washer; ledger P5).
- **#120 — General — `[No code]` — qty 1 — Check box**
  - Ledger source: `P8 (reclassified)` | PDF p.9
  - Decision: Scan the carton barcode to identify the missing model code before import (range hood/hotte; reclassified from Refrigerators per page-1 Key Corrections).
- **#125 — Junkers — `[No code]` — qty 1 — Check box**
  - Ledger source: `P5` | PDF p.9
  - Decision: Scan the carton barcode to identify the missing model code before import (6L gas water heater; ledger P5).
- **#126 — Chaffoteaux — `[No code]` — qty 5 — Check box**
  - Ledger source: `P1` | PDF p.9
  - Decision: Scan the carton barcode to identify the missing model code before import; checklist states 5 units and the table row qty is 5 (match). Brand is printed across two lines as 'Chaffotea / ux'.
- **#134 — Eco Aqua — `[No code]` — qty 4 — Check box**
  - Ledger source: `P8` | PDF p.10
  - Decision: Scan the carton barcode to identify the missing model code before import; checklist states 4 units and the table row qty is 4 (match).
- **#135 — Tatch — `[No code]` — qty 1 — Check box**
  - Ledger source: `P8` | PDF p.10
  - Decision: Scan the carton barcode to identify the missing model code before import (water filter; ledger P8).
- **#138 — Severin — `[No code]` — qty 1 — Check box**
  - Ledger source: `P6` | PDF p.10
  - Decision: Scan the carton barcode to identify the missing model code before import (coffee machine; ledger P6).
- **#148 — Unspecified — `TH212` — qty 2 — Check box**
  - Ledger source: `P6` | PDF p.10
  - Decision: Model code TH212 is present but no brand is written on the sheet; confirm brand from the carton label before import.
- **#149 — Taurus — `[No code]` — qty 1 — Check box**
  - Ledger source: `P6` | PDF p.10
  - Decision: Scan the carton barcode to identify the missing model code before import (food processor / kitchen robot; ledger P6).
- **#150 — Unspecified — `CH020A` — qty 2 — Check box**
  - Ledger source: `P6` | PDF p.11
  - Decision: Model code CH020A is present but no brand is written on the sheet; confirm brand from the carton label before import.

## Possible duplicate pair (2)

- **#39 — Krohler — `KRG-3730-COMB-NF-G` — qty 1 — Verified**
  - Ledger source: `P3` | PDF p.4
  - Decision: Compare the physical carton barcode with #40. The document recommends: if they share the same barcode, merge #39 and #40 into 1 SKU (2 units) before import. This row is Verified; the SKU is printed wrapped over two lines.
  - If barcodes match: merge into 1 SKU (2 units)
- **#40 — Krohler — `KRG370combi NFG` — qty 1 — Check carton**
  - Ledger source: `P8` | PDF p.4
  - Decision: Compare the physical carton barcode with #39. The document recommends: if they share the same barcode, merge #39 and #40 into 1 SKU (2 units) before import. Table description says 'verify if same model as #39'; status is Check carton. SKU printed wrapped over two lines.
  - If barcodes match: merge into 1 SKU (2 units)

## Check-carton rows not on the page-11 checklist (44)

- **#2 — TCL — `P7 (65")` — qty 1 — Check carton**
  - Ledger source: `P1` | PDF p.1
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#3 — TCL — `E6D (65")` — qty 2 — Check carton**
  - Ledger source: `P1` | PDF p.2
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#5 — TCL — `E6D (55")` — qty 5 — Check carton**
  - Ledger source: `P1` | PDF p.2
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#8 — TCL — `75 (43")` — qty 5 — Check carton**
  - Ledger source: `P1` | PDF p.2
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#29 — TCL — `T540TMG` — qty 1 — Check carton**
  - Ledger source: `P8` | PDF p.3
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#44 — Indesit — `BNF601341VNA` — qty 1 — Check carton**
  - Ledger source: `P6` | PDF p.4
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist. Also named in page-1 'Key Corrections' (purged duplicate / model caveat / reclassification / brand-fix context) - check the physical carton.
- **#46 — Indesit — `UINF601021KMA` — qty 1 — Check carton**
  - Ledger source: `P8` | PDF p.4
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#48 — Condor — `CAN450W` — qty 1 — Check carton**
  - Ledger source: `P5` | PDF p.4
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#51 — Royal — `CH-160MS` — qty 2 — Check carton**
  - Ledger source: `P3 (×1) + P5 (×1)` | PDF p.5
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#52 — KGLG — `BD200` — qty 2 — Check carton**
  - Ledger source: `P5 (×1) + P7 (×1)` | PDF p.5
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#63 — TCL — `C1107FLG` — qty 1 — Check carton**
  - Ledger source: `P5` | PDF p.5
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#64 — TCL — `F407TLG` — qty 1 — Check carton**
  - Ledger source: `P5` | PDF p.5
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#65 — TCL — `C1110WDG` — qty 1 — Check carton**
  - Ledger source: `P7` | PDF p.5
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#66 — TCL — `CS12WDG` — qty 1 — Check carton**
  - Ledger source: `P8` | PDF p.6
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#71 — Ganador — `REF. GAN1100` — qty 4 — Check carton**
  - Ledger source: `P4` | PDF p.6
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#73 — Krohler — `KPB95CX` — qty 3 — Check carton**
  - Ledger source: `P3 (×2) + P8 (×1)` | PDF p.6
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#79 — KGLG — `XPB12KG120` — qty 1 — Check carton**
  - Ledger source: `P2` | PDF p.6
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#80 — Golden Star — `XPB1152770` — qty 1 — Check carton**
  - Ledger source: `P5` | PDF p.6
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#81 — Golden Star — `XPB150-2070` — qty 1 — Check carton**
  - Ledger source: `P5` | PDF p.6
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#82 — Fresh — `WM9000TL` — qty 1 — Check carton**
  - Ledger source: `P2` | PDF p.7
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#83 — Fresh — `WM12000TL` — qty 1 — Check carton**
  - Ledger source: `P8` | PDF p.7
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#85 — Skyworth — `F90467NB` — qty 1 — Check carton**
  - Ledger source: `P5` | PDF p.7
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#87 — Globvision — `SBN1086` — qty 2 — Check carton**
  - Ledger source: `P7` | PDF p.7
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#88 — Globvision — `SBN1386` — qty 1 — Check carton**
  - Ledger source: `P7` | PDF p.7
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#93 — Krohler — `MLV1540IG` — qty 1 — Check carton**
  - Ledger source: `P5` | PDF p.7
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist. Also named in page-1 'Key Corrections' (purged duplicate / model caveat / reclassification / brand-fix context) - check the physical carton.
- **#96 — Krohler — `CKS6060BD ELITE` — qty 1 — Check carton**
  - Ledger source: `P5` | PDF p.7
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#98 — Krohler — `FZE7337BL` — qty 3 — Check carton**
  - Ledger source: `P8` | PDF p.7
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#104 — Tatch — `MFA615TP` — qty 1 — Check carton**
  - Ledger source: `P8` | PDF p.8
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#105 — Itimat — `I-07TLL` — qty 2 — Check carton**
  - Ledger source: `P8` | PDF p.8
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#107 — German Lab — `GRL 70` — qty 1 — Check carton**
  - Ledger source: `P2` | PDF p.8
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist. Also named in page-1 'Key Corrections' (purged duplicate / model caveat / reclassification / brand-fix context) - check the physical carton.
- **#110 — Ekan / Krohler — `KL20MOBS5` — qty 4 — Check carton**
  - Ledger source: `P7` | PDF p.8
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#113 — Fitco — `FBH6004GXS` — qty 2 — Check carton**
  - Ledger source: `P2 (×1) + P7 (×1)` | PDF p.8
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#115 — General — `HMS113/-1` — qty 1 — Check carton**
  - Ledger source: `P2` | PDF p.8
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#119 — Infiniton — `CNPA61X` — qty 1 — Check carton**
  - Ledger source: `P8 (reclassified)` | PDF p.9
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist. Also named in page-1 'Key Corrections' (purged duplicate / model caveat / reclassification / brand-fix context) - check the physical carton. Page-1 Key Corrections says this range hood was reclassified from Refrigerators to Cooking & Ventilation; ledger reads 'P8 (reclassified)'.
- **#127 — Daiko — `CAEW8548DK` — qty 2 — Check carton**
  - Ledger source: `P4` | PDF p.9
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#130 — BAP — `GP-6L` — qty 1 — Check carton**
  - Ledger source: `P5` | PDF p.9
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist. Also named in page-1 'Key Corrections' (purged duplicate / model caveat / reclassification / brand-fix context) - check the physical carton.
- **#133 — TCL — `TY-LW8110T` — qty 1 — Check carton**
  - Ledger source: `P7` | PDF p.10
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#136 — Bonomi — `YT2009JL` — qty 11 — Check carton**
  - Ledger source: `P6` | PDF p.10
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#139 — Krohler — `PEAF9512` — qty 2 — Check carton**
  - Ledger source: `P6` | PDF p.10
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#141 — Krohler — `PEAF9411` — qty 1 — Check carton**
  - Ledger source: `P6` | PDF p.10
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#142 — Fitco — `FAF1028DSS` — qty 2 — Check carton**
  - Ledger source: `P6` | PDF p.10
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#144 — Genial — `GBM5130SBS` — qty 2 — Check carton**
  - Ledger source: `P6` | PDF p.10
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#145 — Genial — `KTSM6423` — qty 1 — Check carton**
  - Ledger source: `P6` | PDF p.10
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.
- **#147 — Tatch — `007117` — qty 1 — Check carton**
  - Ledger source: `P6` | PDF p.10
  - Decision: Confirm the carton label/SKU matches this table row; status is 'Check carton' in the table but the row is NOT in the page-11 checklist.

## Internal placeholder SKUs — physical label/barcode required (8)

These eight rows had no model code on the handwritten sheet. They have been given **internal** `PH-...` codes solely so the import is lossless. These are NOT manufacturer model numbers. Scan the carton and replace each with the real SKU before treating the product as sellable.

- **#86** — `[No code]` → **`PH-086-LAU-TAT-P5`** — physical label check required: yes
- **#120** — `[No code]` → **`PH-120-VEN-GEN-P8`** — physical label check required: yes
- **#125** — `[No code]` → **`PH-125-WAT-JUN-P5`** — physical label check required: yes
- **#126** — `[No code]` → **`PH-126-WAT-CHA-P1`** — physical label check required: yes
- **#134** — `[No code]` → **`PH-134-FIL-ECO-P8`** — physical label check required: yes
- **#135** — `[No code]` → **`PH-135-FIL-TAT-P8`** — physical label check required: yes
- **#138** — `[No code]` → **`PH-138-SMA-SEV-P6`** — physical label check required: yes
- **#149** — `[No code]` → **`PH-149-SMA-TAU-P6`** — physical label check required: yes

## Source-document discrepancies (no data change made)

- Page-1 summary claims '89 SKUs matched to verified catalog specs' and '61 SKUs flagged for carton / label check', but the 150-row table actually has 95 Verified and 55 Check rows (45 Check carton + 10 Check box). Raw text token counts independently confirm 95/45/10. Use the table counts, not the page-1 summary.
- #129 (checklist P7, 'quantity scribbled over; counted as 1'): table row qty 1, Verified, ledger 'P7 (check qty)'. The table carries a 'check qty' note but does not itself say the quantity was scribbled over; qty 1 matches the checklist.
- #74 (checklist P8, 'quantity overwritten; counted as 1'): table row qty 1, Verified, ledger 'P8 (KP1395 CX)'. No overwritten-quantity annotation appears in the table row; only the alternate code KP1395 CX. Qty 1 matches the checklist.
- #10: checklist says both return items were 'marked retour on the manual sheet', but this row's ledger reads 'P2 (×1) + P4 (×2) + P8 (×1 ret.)' (abbreviated 'ret.') and its description says '1 unit marked Return'. Only #6 literally reads 'P8 (retour)'. Exclusion scope per document: 1 of 4 units for #10; full qty 1 for #6.
- Checklist page references are handwritten-ledger sheet numbers, not PDF page numbers: #6/#10 listed P8 appear on PDF p.2, #40 listed P8 and #39 listed P3 both appear on PDF p.4, #74 listed P8 appears on PDF p.6, #86 on PDF p.7, #120/#125/#126 on PDF p.9, #134/#135/#138/#148/#149 on PDF p.10, #129 listed P7 appears on PDF p.9, #150 on PDF p.11. The 'page' field in this JSON is the PDF page; the ledger sheet is in 'ledger' / 'checklist_page_ref'.
- Line-wrap artifacts in extracted text (not data errors): #39 'KRG-3730- / COMB-NF-G', #40 'KRG370combi / NFG', #126 brand 'Chaffotea / ux', #148 and #150 brand 'Unspecifie / d', #44 'BNF601341VN / A', #46 'UINF601021KM / A', #96 'CKS6060BD / ELITE', and #119/#120 ledger 'P8 (reclassifi / ed)'. Values above are the unwrapped printed values.
- No quantity discrepancy found for #126 (checklist 5 units; table 5), #134 (checklist 4 units; table 4), #6 (checklist 1 unit; table 1), #10 (checklist 1 of 4 units; table qty 4 with 1 marked ret.), or the duplicate pair #39+#40 (1+1=2 units as the checklist's merge target).
- Agent limitation: page-11.png could not be visually decoded by this model (image input unsupported). The page-11 checklist was read from extracted text lines 1817-1831; all table rows were independently parsed from the full extracted text (150/150 rows parsed with a status).
