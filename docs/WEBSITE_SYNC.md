# Website Sync — How the ERP talks to your website

The ERP and the website are **decoupled on purpose**: they never talk to
each other directly over the network. Instead they exchange two simple
**JSON files**. This works with *any* website technology (WordPress,
WooCommerce, Shopify, custom PHP/Node site…) and cannot break if the
website is offline.

```
┌─────────────┐   website_catalog.json    ┌──────────────────┐
│             │ ─────────────────────────▶ │                  │
│  TAJ ERP    │      (upload / copy)       │     WEBSITE      │
│  (Settings) │                            │                  │
│             │ ◀───────────────────────── │                  │
└─────────────┘   price_updates.json       └──────────────────┘
                   (download / copy)
```

---

## 1. Export: ERP → Website (`website_catalog.json`)

**Where:** Settings → Website Sync → **Export Catalog for Website...**

This writes a snapshot of every sellable product (archived products
excluded). Upload this file to the website (via its admin panel, FTP, or
whatever import mechanism the site offers).

### File format

```json
{
  "exported_at": "2026-08-25T22:00:00+01:00",
  "product_count": 2,
  "products": [
    {
      "sku": "SPLIT-12000",
      "name": "Split Inverter 12000 BTU",
      "sale_price": 4999.0,
      "vat_rate": 20.0,
      "stock": 7,
      "active": true,
      "category": "Climatiseur",
      "brand": "Taj"
    }
  ]
}
```

| Field        | Meaning                                        |
|--------------|------------------------------------------------|
| `sku`        | Unique product code — **the join key**         |
| `sale_price` | Selling price **excluding VAT**, in DH         |
| `vat_rate`   | VAT percentage for display                     |
| `stock`      | Current physical quantity in the ERP           |
| `active`     | `false` = product should be hidden on the site |
| `category` / `brand` | Optional labels for filtering          |

> The website decides what to do with `stock`: hide the "Add to cart"
> button at 0, show "sur commande", etc.

---

## 2. Import: Website → ERP (`price_updates.json`)

**Where:** Settings → Website Sync → **Import Web Price Updates...**

When prices change on the website side (promotions, negotiated web
prices), export them from the site as this file and load it into the
ERP. Both formats below are accepted:

```json
[
  { "sku": "SPLIT-12000", "sale_price": "4599.00" },
  { "sku": "SPLIT-9000",  "sale_price": "3899.50" }
]
```

or wrapped:

```json
{
  "products": [
    { "sku": "SPLIT-12000", "sale_price": "4599.00" }
  ]
}
```

### What happens on import

- Prices are validated as positive decimal numbers; bad entries are
  **reported, not fatal**.
- Unknown SKUs are skipped and listed in the result dialog.
- Unchanged prices are ignored.
- Every actual change is written to the **audit log** with before/after
  values (who, when, old price → new price).
- A summary dialog shows: updated count, unknown SKUs, errors.

---

## 3. Automation options (later, no code change needed in the ERP)

Because everything is files, you can automate without touching the ERP:

1. **Scheduled export**: run the export daily; a scheduled task copies
   `website_catalog.json` to the web server (FTP/SFTP/scp).
2. **Website-side cron**: the site regenerates `price_updates.json`
   nightly from its own database.
3. **Shared folder**: put both files in a Dropbox/OneDrive folder both
   sides can reach.

## 4. Future upgrade path

If the website later exposes a REST API (e.g., WooCommerce REST), the
same `WebsiteSyncService` methods can be called from a small script that
pushes/pulls JSON over HTTP instead of files — the ERP data model does
not change.