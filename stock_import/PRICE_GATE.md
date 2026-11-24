# Price gate for stock import (NEEDS PRICING)

Authoritative contract: `docs/PINNED_PRICE_CONTRACT.md`. This note only describes
how the import tooling applies it; the contract itself is never edited here.

- A missing `prices.csv`, a blank/zero `sale_price`, or an unconfirmed VAT rate
  on an unpriced row is a **NEEDS PRICING warning**, not an import blocker.
- The importer may create products with `sale_price = 0.00`, no `pinned_price`,
  `effective_price = 0`, `priced = false`, and state **DRAFT**. Unpriced products
  are hidden from phone catalog/invoice pickers and ERP POS prefill until a pin
  is entered.
- Import tooling **never sets a non-empty pinned_price**. Relay-shaped payloads
  include `pinned_price: ""` and `priced: false` for unpriced rows; no ERP write
  call passes a pin.
- Retail prices must come from the business owner. No price is invented,
  inferred, or copied from supplier pro-forma / cost sheets. Negative values,
  formula fragments, non-numeric text, duplicate/malformed price rows, and
  cost/supplier price columns remain hard blockers.
- VAT may use the ERP default `20.00` with an explicit unverified warning until
  the authoritative rate is entered.

Other gates are unchanged and remain hard blockers: all 8 placeholder label
confirmations, every unresolved human decision (including the #39/#40 pair),
the 95/55 source errata acknowledgement, relay full-rebuild safety, and explicit
`--apply` / relay-push approval via `stock_import/APPLY_APPROVED.txt` containing
exactly `APPROVED BY HUMAN`. Dry-run planning is always allowed and is the
default for `scripts/import_products.py`.
