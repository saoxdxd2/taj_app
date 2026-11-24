# Pinned price contract (v1)

Approved scope: ERP desktop (`taj_app`) and phone PWA/relay (`tajfroid-mobile`).
The `tajfroid` website is intentionally untouched.

## Meaning

- A **pinned price** is the authoritative retail price for a product. It can be set from the ERP or from the phone, with identical effect.
- `sale_price` remains the base ERP price and may be `0` for imported stock.
- `effective_price = pinned_price when present and non-empty, otherwise sale_price`.
- `priced = effective_price > 0`.
- Setting a pin activates a DRAFT product so it becomes sellable. Clearing a pin does not change state; a cleared pin falls back to `sale_price`.

## Field names (must be identical everywhere)

Catalog payload product object:

```text
sku, name, sale_price, pinned_price, effective_price, priced,
vat_rate, stock, active, category, brand
```

- `sale_price`: base price as decimal string (may be `"0"`).
- `pinned_price`: decimal string when pinned, `""` when explicitly cleared, `null` only for legacy/unknown state.
- `effective_price`: decimal string; the price all sales surfaces must use.
- `priced`: boolean (`effective_price > 0`). A product with `sale_price > 0` and no pin is priced.

Wire casing follows each existing endpoint's convention; logical field names are identical:
- `/api/catalog` and ERP `PUT /api/agent/catalog`: `snake_case` (`pinned_price`, `effective_price`).
- `/api/products` and `/api/products/manage`: camelCase (`pinnedPrice`, `effectivePrice`, `priced`).

The phone normalizes both shapes before rendering.

ERP model: `Product.pinned_price = Numeric(12, 2), nullable=True`.

Relay DB: `catalog.pinned_price TEXT NULL` — `NULL` = never set, `''` = explicitly cleared, non-empty = pin.

## Visibility

- Unpriced products are **hidden from sales surfaces**: phone `/api/catalog` default response, phone invoice product picker, ERP POS invoice prefill.
- Unpriced products remain **visible in pricing surfaces**: ERP Inventory list, phone Inventory list, and a phone "Needs pricing" view.
- `GET /api/catalog?include_unpriced=1` and `GET /api/products?include_unpriced=1` bypass the filter. When the flag is present, skip the 304 branch so a mode switch cannot serve a stale response.
- A deliberately zero retail price is not supported; `0` means unpriced.

## Write path (phone)

`PUT /api/products/manage?sku=<sku>` body:

```json
{"id": "<uuid per edit>", "pinnedPrice": "149.00", "baseCatalogVersion": 123}
```

- omitted / `null` `pinnedPrice`: preserve the existing pin.
- `""`: explicitly clear the pin (store `''` in relay and clear the ERP pin on pull).
- decimal string: validate and set; also set `active = 1`.
- Keep the existing `baseCatalogVersion` check before any write; stale base -> 409 with no write and no version bump.
- Bump `catalog_meta` with `lib.CatalogMetaBumpSQL` on a successful pin write.

## Propagation (phone -> ERP)

- The phone pin write bumps `catalog_meta.version`.
- The desktop pull (`GET /api/catalog?version=N`) receives the changed product with `pinned_price`.
- ERP pull applies remote pins by SKU:
  - remote `null` (legacy/unknown) -> leave the local pin unchanged;
  - remote `""` -> clear the local pin;
  - remote non-empty decimal -> set the local pin (and activate a DRAFT product).
- Only run this apply for products actually present in the pulled snapshot; never clear pins for SKUs missing from the response.
- Compare each remote value with `last_pushed_pins` from the ERP checkpoint. Apply only values that changed since the last ERP push, so a pin entered locally after that push is not cleared by stale relay data. A legacy checkpoint with no `last_pushed_pins` map ignores remote clears.

## Propagation (ERP -> phone)

- ERP catalog push always sends the `pinned_price` key: a decimal string when pinned, `""` when cleared/unset. It never sends `null`.
- The relay upsert preserves an existing pin only when the key is omitted or `null` (legacy clients); `""` explicitly clears it and a decimal string sets it.
- The desktop rebuild must NOT `DELETE FROM catalog`; it must delete only SKUs absent from the incoming snapshot, then upsert. Combined with the `baseRevision` check, this prevents a stale push from wiping phone-entered pins.
- Statement count stays O(1) round trips via one `ExecuteBatch`.

## Conflict safety

- Keep `baseRevision` on the desktop push and the existing 409 retry in `sync.py`.
- Keep `baseCatalogVersion` on phone writes and the existing 409 contract.
- The two tokens are different; do not conflate them.
- A pin write from either side always changes the catalog content hash/version.

## Import workflow

- The warehouse import may create products with no price (`sale_price = 0`, `pinned_price = NULL`, state DRAFT).
- Import tooling must not invent prices and must not set `pinned_price`.
- The readiness gate treats missing prices as a **NEEDS PRICING** warning, not an import blocker. Blocking happens at the sales surface until a pin is entered.

## Non-goals

- No website pricing changes (`sale_price_website` stays as-is).
- No APK build/sign/install in this batch.
