# Task Manifest

Task ID: T-0006

Title: Inventory

Status: Closed

---

Business Objective

Establish the Inventory domain to represent anything the company can sell or consume, ensuring accurate tracking of physical products, consumables, and services while enforcing rigorous financial boundaries.

---

Engineering Objective

Implement the `Product`, `Brand`, and `Category` models with state machine lifecycle controls (Draft, Active, Archived). Enforce the `11_DATABASE_STANDARD.md` mandate restricting floating-point money by leveraging exact Decimal (`Numeric`) representations for all prices and VAT. 

---

Dependencies

- T-0002 (Database)
- T-0005 (Suppliers - for ForeignKey reference)

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

- `Product`, `Brand`, `Category` models created.
- `ProductState` enum handles the `Draft -> Active -> Archived` transition.
- `ProductType` enum created for business differentiation.
- Financial fields (`purchase_price`, `sale_price`, `vat_rate`) use `Numeric/Decimal`.
- Negative prices are strictly forbidden at the service level.
- Permanent deletion is forbidden; products move to `Archived`.

---

Deliverables

- `src/modules/inventory/models.py`
- `src/modules/inventory/services.py`

---

Database Impact

Major (Added Core Inventory schemas: Product, Brand, Category with inter-module foreign keys)

---

Security Impact

None

---

Audit Impact

Minor (Prepared for audit generation on product modification/state change)

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

The Inventory foundation has been strictly initialized according to the standard. State transitions explicitly forbid bypassing the database constraints, ensuring no historical records are invalidated.
