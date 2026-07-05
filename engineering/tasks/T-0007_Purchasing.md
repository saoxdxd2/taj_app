# Task Manifest

Task ID: T-0007

Title: Purchasing

Status: Closed

---

Business Objective

Establish the Purchasing domain to manage supplier invoices, purchases, and initial stock entries. Purchasing represents the primary mechanism for increasing physical inventory and supplier balances.

---

Engineering Objective

Implement the `Purchase` and `PurchaseItem` models. Define the `PurchasingService` to enforce the Draft -> Validated state machine. Scaffold the strict validation boundaries required for atomic transactions (where validating a purchase will synchronously trigger inventory, audit, and financial journal entries).

---

Dependencies

- T-0002 (Database)
- T-0005 (Suppliers - for ForeignKey reference)
- T-0006 (Inventory - for ForeignKey reference)

---

Required Documents

- 10_BUSINESS_ARCHITECTURE.md
- 11_DATABASE_STANDARD.md
- 08_PYTHON_CODING_STANDARD.md

---

Required EDRs

None.

---

Acceptance Criteria

- `Purchase` and `PurchaseItem` models created with `Decimal` tracking for all amounts.
- `PurchaseState` enum implemented.
- Relationships established referencing `Supplier` and `Product` models.
- `PurchasingService` enforces the rule that items cannot be appended after validation.
- `PurchasingService` enforces non-negative cost and quantity invariants.

---

Deliverables

- `src/modules/purchasing/models.py`
- `src/modules/purchasing/services.py`

---

Database Impact

Major (Added Purchase and PurchaseItem schemas linking Suppliers to Products)

---

Security Impact

None

---

Audit Impact

Major (Outlined hooks for the atomic transaction required upon Purchase Validation)

---

Documentation Required

Yes (This document and PROJECT_MEMORY.md)

---

Tests Required

None (Unit tests deferred to dedicated QA phase)

---

Estimated Complexity

Medium

---

Current Phase

Closed

---

Progress

100%

---

Notes

The Purchasing foundation is set. The actual linkage triggering Stock Movements and Financial Journals is intentionally marked as a strictly required TODO inside `PurchasingService.validate_purchase` to ensure cross-domain transactional safety is maintained as those domains are built.
