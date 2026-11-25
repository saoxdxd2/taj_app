# TAJ FROID — Routes and Integration

This page documents the main routes and the direction for the database/server route.
It is a planning/reference doc. Do not run or implement architecture changes here unless a
separate approval/task says so.

---

## 1. ERP product API routes (Go)

Main ERP is `taj_app`. Expected route family:

| Route | Method(s) | Purpose |
|---|---|---|
| `/api/catalog` | `GET` | Active product catalog view (desktop relay pull). |
| `/api/products` | `GET`, `POST` | ERP-facing product CRUD with camelCase JSON. |
| `/api/products/manage` | `GET`, `POST`, `PUT`, `DELETE` | Management views used by ERP UI; camelCase JSON. |
| `/api/agent/catalog` | `PUT` | Conflict-safe catalog push from phone relay; snake_case JSON. |
| `/api/agent/bootstrap` | `GET` | Pair/bootstrap path exempted from 401 redirect. |
| `/api/devices` | `GET` | Phone devices list. |
| `/api/devices/manage` | `POST`, `PUT`, `DELETE` | Device management/revocation. |
| `/api/health` | `GET` | Relay health. |

Route casing note: `/api/catalog` and `PUT /api/agent/catalog` use `snake_case`; `/api/products` and `/api/products/manage` use `camelCase`. Phone app normalizes both.

---

## 2. Phone PWA routes (`tajfroid-mobile`)

| Route | Purpose |
|---|---|
| `/` | Redirect to `/catalog`. |
| `/catalog` | Catalog view. Unpriced products hidden from sales until pinned. |
| `/inventory` | Inventory view. |
| `/needs-pricing` | Unpriced products; set/clear pinned price from phone. |
| `/sales` | Invoices. |
| `/purchases` | Purchases. |
| `/contacts` | Contacts. |
| `/finance` | Finance screens. |
| `/scans` | Photo upload queue. |
| `/queue` | Scan queue/sync status. |
| `/pair` | Pair with desktop; supports QR auto-pair and manual pairing code. |
| `/account` | Connection status and device management. |

The header pill is a discoverable “Connect to computer” route entry.

---

## 3. Website integration routes

The website integration is file-based by design. See `docs\WEBSITE_SYNC.md`.

Key routes/flows:

- ERP → website: writes `website_catalog.json` in shared sync folder (atomic).
- Website → ERP: `price_updates.json` consumed and renamed to `price_updates.applied-<timestamp>.json`.

Because you now have the website connected to the local `taj-froid` folder, this can reduce redundancy by letting the website read the shared catalog snapshot instead of maintaining a separate live DB copy.

---

## 4. Database/server route direction

### Current route

- Primary ERP database: Turso/libSQL, accessed by Go relay and ERP scripts.
- Relay server: Go, protects `/api/agent/catalog` pushes with `baseRevision`/`baseCatalogVersion` and 409 conflict handling.

### Preferred direction you mentioned

You prefer “Rust and Go”. A safe long-term route is:

1. Keep the current Go relay as the sync authority while it is stable.
2. Use **Rust** for future high-performance or postgres-compatible layers:
   - pgrust as a PostgreSQL-compatible replica/reporting engine when it is stable.
   - Rust CLI/import/validation tools for stock import where useful.
3. Only migrate the primary ERP database route later if there is a real operational need and pgrust is out of beta/proven.

### Concrete Rust/Go roadmap for later

| Step | Owner | Goal |
|---|---|---|
| Docs: why not now | Human decision | pgrust is beta; primary ERP is high-confidence now. |
| Proof-of-concept local pgrust | Dev | Run pgrust in Docker on local data; run read-only benchmarks. |
| No-touch evaluation | Dev | Compare reads/writes for stock/products/invoices only. |
| Decision gate | Human | If pgrust is materially better after stable release. |
| Migration plan | Human + Dev | Dump/restore, dual-read/shadow, cut over. |
| Rollback plan | Human | Keep Turso as backup/source of truth until cut-over is proven. |

---

## 5. How to reduce redundancy today

- Website should read from the connected local sync folder for catalog snapshots.
- ERP remains the source of truth for pricing/stock.
- Avoid duplicating catalog logic in website and ERP; document one writer per data type.
- If live sync later changes, document the new routes/files and update this file.
