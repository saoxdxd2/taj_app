# TAJ FROID ERP — MASTER PLAN (v2, Definitive)

> Status: APPROVED-BY-ANSWERS (44/44 questionnaire answered by developer/owner)
> Scope: finish the desktop ERP, add website sync, analytics, invoicing, infrastructure monitoring — production-ready, one-time quality build.
> This document supersedes conflicting roadmap info in docs/Volumes where applicable.

---

## 1. Confirmed Context (from owner answers + codebase inspection)

### Business reality
- **Users:** exactly 2 — the developer (sao) and the boss (store owner). Single Windows PC. No multi-user management needed; keep auth simple but keep the existing login/RBAC skeleton (it already works and costs nothing).
- **Sales:** in-store only. Payment methods: **cash, checks, bank transfers (virements)**. No online sales — tajfroid.com is a **showcase catalog** that redirects visitors to call/WhatsApp the boss.
- **Services sold** alongside products (e.g., clim installation) → must be billable line items.
- **Returns:** refund OR exchange; defective units sent back to factory for repair. **Warranty:** normally 1 year, motors up to 10 years → warranty tracking with per-item end dates.
- **Advance payments ("bons"):** customer pays a deposit (sometimes by check), receives goods later → deposit/layaway tracking + check due-date calendar.
- **Invoicing today:** hand-made in Excel, exported to PDF (samples: FACTURE N°16, N°17). Boss complains about complexity and speed → the app must beat Excel on math, speed, and simplicity.
- **Pricing:** sell price is NOT fixed — boss registers the actual sold price per transaction, and the actual buy price, so profit analysis is exact.
- **Currency:** MAD (DH) only.
- **Data:** fresh start; only current stock will be registered initially. Clients/suppliers keep: ICE, payment terms, contact info, trade stats.

### Products
- Hundreds → thousands of SKUs (from scotch tape to generators).
- **Dynamic, user-definable attributes** (BTU, capacity, sound level, max cold °F/°C, energy efficiency…) — created/modified/deleted by the user, used as **filters on the website**. Nothing hard-coded.
- No barcode scanning for now; products identified by **référence**. Label printing optional later.
- Serial numbers: not required globally; warranty tracked at sale level.

### Website (tajfroid.com) — inspected
- **Nuxt 4 + Nitro (Vercel preset), Drizzle ORM + libsql/Turso, better-auth (Google OAuth + local accounts), Tailwind, i18n fr/en/ar, nuxt-security, PWA, Resend email, Gemini AI assistant, WASM engines (PDF/CSV/image/email).**
- Admin UI exists (`pages/admin/**`, `ProductModal.vue`), Nitro scheduled tasks exist, PM2 blue/green alt deploy documented.
- Env vars (names only): `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `NUXT_SESSION_PASSWORD`, `AUTH_SECRET`, `GOOGLE_CLIENT_ID/SECRET`, `GEMINI_API_KEY`, `RESEND_API_KEY`, `SMTP_*`, `NUXT_ADMIN_EMAIL`, `BETTER_AUTH_URL`.
- **No products on the site yet** — catalog is empty and in testing. Perfect timing: we design the sync before content exists.

### Infrastructure
- Domain: **tajfroid.com @ Porkbun**, expires **2027-03-07** (364 days), Porkbun **API access is enabled** → we can poll renewal/expiry programmatically.
- Hosting: **Vercel free tier**. DB: **Turso (free tier)**, upgradeable.
- Internet at shop: reliable but sometimes slow → offline-first is mandatory.
- AI assistant on site: local-key mode works; API-key mode currently errors ("no api"). Key must be provisioned **out-of-band (never in git)**.

---

## 2. Architecture (target)

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│  DESKTOP ERP (this repo)    │        │  WEBSITE (taj_froid repo)    │
│  PySide6 + SQLAlchemy 2.0   │        │  Nuxt 4 + Nitro on Vercel    │
│  SQLite (LOCALAPPDATA)      │        │  Drizzle + Turso (libsql)    │
│  ┌───────────────────────┐  │  HTTPS │  ┌────────────────────────┐  │
│  │ Sync Engine           │──┼───────►│  │ /api/erp/* (NEW)       │  │
│  │  - outbox queue       │  │  JSON  │  │  x-erp-api-key auth    │  │
│  │  - retry/backoff      │  │        │  │  upsert categories,    │  │
│  │  - offline tolerant   │  │        │  │  brands, products,     │  │
│  └───────────────────────┘  │        │  │  prices, promos, avail │  │
│  ┌───────────────────────┐  │        │  └────────────────────────┘  │
│  │ Infra Monitor         │──┼───────►│ Porkbun API (domain expiry)  │
│  └───────────────────────┘  │        │ Vercel status (site uptime)  │
└─────────────────────────────┘        └──────────────────────────────┘
```

**Sync model decision (final):** ERP is the **single source of truth** for catalog data (products, categories, brands, prices, promos, availability, news). The website never writes back catalog data (no online sales). Push-based with a local **outbox queue**:
- Trigger points: on every committed change (enqueue), flush on app close/minimize, plus a periodic loop (default 10 min, user-adjustable in Settings).
- If offline: queue persists in SQLite; flushes automatically when connectivity returns. App never blocks on network.
- No WebSockets (not needed — no reverse sync of importance).

**Auth for the ERP API:** dedicated random 256-bit API key generated once, stored in Windows Credential Manager (via `keyring`) on the app side and as a Vercel env var on the site side. Never in git, never in the DB file. Rate-limited + constant-time comparison on the site.

---

## 3. Desktop ERP — Feature Plan

### 3.1 Core modules (finish & harden)
| Module | Work |
|---|---|
| Products | Dynamic attributes engine (user-defined attribute defs + per-product values, JSON-backed, filterable), référence unique, categories/brands CRUD, images, cost price history |
| Inventory | Current stock registration, stock movements ledger, min-stock alerts, "what exists / what's lacking" reorder view, seasonality tags |
| Clients/Suppliers | ICE, payment terms, contact info, trade stats (per-client sales history), credit notes |
| Sales | Register actual sold price per line, actual cost captured at sale time → exact margin; payment method (cash/check/virement); services as line items; advance/deposit ("bon") flow with balance settlement |
| Checks calendar | All incoming/outgoing checks with due dates; friendly reminders in-app (dashboard banner + notifications) N days before due; status lifecycle (pending → deposited → cleared/bounced) |
| Returns | Refund or exchange flows; stock re-entry; defective-unit tracking ("sent to factory", repaired/replaced); warranty end-date per sold item (default 1y, motors 10y — configurable per product category) |
| Purchases | Record supplier purchases with real buy prices (feeds cost history); optional simple PO later — not a priority |
| Expenses | Manual entries, optional per owner decision: transport, salaries, rent, misc — each with category; feeds true net profit |
| Invoicing | **In-app facture generator** (see 3.2) |
| Analytics | See 3.3 |

### 3.2 Invoicing (must beat Excel)
- PDF generation via the existing `core/pdf_engine.py` (WeasyPrint) with a template **matching the current Excel facture layout**: header TAJ FROID + legal block (RC 180311, IF 72066838, Patente 46208127, CNSS 4700437, ICE 003947029000043, address), client block with ICE, line items (désignation, QTÉ, PRIX, TOTAL), TVA 20%, total in words in French ("Arrêtée la présente facture à la somme de…"), payment mention (PAYÉ PAR CHECK N°… / VIREMENT / ESPÈCES), facture numbering N°XX-YY auto-increment per year.
- One-screen fast entry: type référence → autocomplete → qty → done. Target: < 10 seconds for a 3-line invoice. Keyboard-first.
- Export PDF to a chosen folder and/or open print dialog (Canon driver handles printing — app only exports/prints).
- Every invoice is immutable once validated; corrections via avoir (credit note) — matches the archive-only doctrine.

### 3.3 Analytics & reports
- **Profit engine:** margin per line (sold price − actual cost), per product, category, brand, client, month, season. Gross profit → minus expenses → net profit.
- Dashboards (PySide6 + QtCharts or matplotlib): monthly revenue/profit, top products, dead stock, stock valuation, checks due timeline, expenses breakdown.
- Report export: PDF + Excel (openpyxl/xlsxwriter).
- **Forecasting (Phase 6, optional):** TimesFM (Google open-source) running locally for seasonality-aware demand hints ("clims sell Jun–Aug"). Forward-pass only initially; fine-tuning (LoRA) is a stretch goal. Must never block or slow the app — runs as an optional background task, results are advisory only.

### 3.4 Infrastructure monitor (in-app)
- **Domain:** poll Porkbun API (key stored in Credential Manager) → expiry countdown; warn in-app + optional email (via Resend from the website or SMTP) 30 days before. Current expiry 2027-03-07.
- **SSL cert expiry** (standard TLS check), **website uptime** (HEAD request to tajfroid.com), **Vercel/Turso reachable** flags.
- All checks cached; failures degrade gracefully (offline shop PC must never show false alarms).

### 3.5 Simplifications (approved)
- Keep login + basic roles but only 2 accounts; remove multi-user complexity from UI flows.
- No barcode hardware support for now (référence-based entry; label printing deferred).
- Single workstation; no LAN sync. (Phone app for the boss: explicitly out of scope until ERP v1 is delivered.)

---

## 4. Website Sync — API Design (new `/api/erp/*` in taj_froid repo)

- `POST /api/erp/auth/verify` — validate key, return site schema version.
- `PUT /api/erp/categories` / `brands` — bulk upsert (ERP manages these automatically, as requested: "reliable API that can manage the admin from the website auto like creating categories and brands").
- `PUT /api/erp/products` — bulk upsert: référence (natural key), name (fr/en/ar), descriptions, brand, category, attributes (→ site filters), sell price, promo price + window, **availability** (in-stock / low / out — exact counts hidden from public, visible to admin only), images (uploaded to Vercel Blob or existing media path), active/archived.
- `POST /api/erp/news` — announcements/posts.
- `GET /api/erp/status` — last-sync state, schema version, site health (also consumed by the ERP infra monitor).
- Idempotency: every request carries an `erp_sync_id` (UUID from the outbox row); site dedupes.
- Conflicts: none by design — ERP wins for catalog data; site-side manual edits to synced fields are overwritten (documented in site admin UI).
- i18n: FR is authored in the ERP; EN/AR optional fields — site falls back to FR when empty.

---

## 5. Quality & Process (approved)

1. **Repo cleanup (approved):** remove `data/taj_app.db`, `error.txt`, `trace.txt`, `text`; move `src/crypto-research/` out of this repo (separate project); delete or fill empty scaffolding dirs.
2. **Tests:** expand from 7 → comprehensive: unit (services: sales, payments, checks, returns, warranty, profit, sync outbox), integration (invoice PDF snapshot, migration chain, sync flush offline/online), UI smoke tests (QTbot) for critical flows (fast invoice entry, product create). Multiple parallel test agents will be used to reach production confidence.
3. **CI:** GitHub Actions — pytest on every push + before-release build; PyInstaller build artifact check.
4. **Performance budget:** app cold start < 3s on the shop PC; invoice entry interactions < 100ms; sync never blocks UI (background QThread).
5. **Security:** API keys/secret material only in Windows Credential Manager; Argon2id logins stay; audit trail stays immutable.
6. **Process:** keep the `engineering/` governance (task files, PROJECT_HEALTH updates) but lightweight — one task file per phase, updated as we go.
7. **Gemini key provisioning:** out-of-band handoff (never committed); app/site read from env/credential store; clear error + disable when absent.

---

## 6. Phased Roadmap (build order)

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **0 — Hygiene** | Repo cleanup, CI green, test foundation expanded, PRAGMA listener per-engine | CI passing, clean tree |
| **1 — Core ERP** | Products + dynamic attributes, stock ledger, clients/suppliers (ICE), purchases, sales with real prices, services, deposits ("bons"), checks calendar, returns + warranty | All core flows tested; boss can register full catalog + current stock |
| **2 — Invoicing** | Facture PDF matching current format, fast entry screen, numbering, print/export | Invoice indistinguishable from Excel output; <10s for 3-line invoice |
| **3 — Finance & Analytics** | Expenses, profit engine, dashboards, PDF/Excel reports | Margin per product/client/month verified against hand-calculated samples |
| **4 — Website Sync** | `/api/erp/*` on site + ERP sync engine + admin-auto categories/brands/products/promos/availability + news | Site catalog populated from ERP; offline queue proven; key in Credential Manager |
| **5 — Infra Monitor** | Porkbun domain expiry, SSL, uptime checks, warnings (in-app + email) | Warning fires in test with mocked near-expiry date |
| **6 — Polish & Extras** | TimesFM forecasting (optional), label printing (optional), installer/Inno Setup final, UAT with boss, performance tuning | Boss signs off on final build |

---

## 7. Out of scope (v1) — recorded to prevent scope creep
- Phone/companion app for the boss (revisit after v1 delivery).
- Online sales/checkout (site stays showcase-only).
- Barcode scanning hardware.
- Multi-PC / LAN mode.
- Accounting-standard bookkeeping (this is management accounting, not fiscal accounting).
- LoRA fine-tuning of TimesFM (stretch goal only).