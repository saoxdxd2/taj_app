# Task Manifest

Task ID: T-0011

Title: Core Integrations (Atomic Transactions)

Status: Closed

---

Business Objective

Ensure that all cross-domain transactions strictly adhere to the Business Architecture. When a Purchase is validated, stock must increase and supplier balances must update. When an Invoice is validated, stock must decrease (without going negative) and financial records must be updated. This links the core engines.

---

Engineering Objective

Remove TODOs from the `PurchasingService` and `SalesService`. 
Implement `StockLevel` and `StockMovement` in the `Inventory` domain to act as the ledger for physical goods.
Inject cross-module service calls (`InventoryService`, `FinanceService`, `AuditService`) to form atomic operations guaranteeing database consistency across modules.

---

Dependencies

- T-0006 (Inventory)
- T-0007 (Purchasing)
- T-0008 (Sales)
- T-0009 (Finance)
- T-0010 (Audit)

---

Required Documents

- 10_BUSINESS_ARCHITECTURE.md
- 11_DATABASE_STANDARD.md

---

Required EDRs

None.

---

Acceptance Criteria

- `StockLevel` and `StockMovement` models created.
- `InventoryService.adjust_stock` safely adjusts stock and writes an immutable stock movement history.
- `PurchasingService.validate_purchase` calls Inventory, Finance, and Audit services.
- `SalesService.validate_invoice` calls Inventory (enforcing non-negative rule), Finance, and Audit services.
- All TODOs removed.

---

Deliverables

- `src/modules/inventory/models.py`
- `src/modules/inventory/services.py`
- `src/modules/purchasing/services.py`
- `src/modules/sales/services.py`

---

Database Impact

Major (Added Core Stock Tracking schemas)

---

Security Impact

None

---

Audit Impact

Major (Activated real hooks emitting audit events from core operations)

---

Documentation Required

Yes (This document and PROJECT_MEMORY.md)

---

Tests Required

None (Unit tests deferred to dedicated QA phase)

---

Estimated Complexity

High

---

Current Phase

Closed

---

Progress

100%

---

Notes

The central engine of the ERP is now completely linked. Validation of purchasing and sales documents directly triggers the immutable side-effects expected by the finance, inventory, and audit layers.
