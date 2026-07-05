# Task Manifest

Task ID: T-0008

Title: Sales

Status: Closed

---

Business Objective

Establish the Sales domain to manage legal financial documents (invoices) and quotations. This domain generates revenue and represents the primary mechanism for reducing physical inventory.

---

Engineering Objective

Implement the `Invoice`, `InvoiceItem`, `Quotation`, and `QuotationItem` models. Define the `SalesService` to enforce the state machine (Draft -> Validated). Scaffold the strict validation boundaries required for atomic transactions (where validating an invoice will synchronously trigger inventory reduction and financial journal entries).

---

Dependencies

- T-0002 (Database)
- T-0004 (CRM - for Customer reference)
- T-0006 (Inventory - for Product reference)

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

- `Invoice` and `Quotation` models created alongside their respective line items, strictly utilizing `Decimal`.
- `InvoiceState` and `QuotationState` enums implemented.
- Cross-domain relationships established referencing `Customer` and `Product` models.
- `SalesService` enforces the fundamental invariant: Modification after validation is forbidden.

---

Deliverables

- `src/modules/sales/models.py`
- `src/modules/sales/services.py`

---

Database Impact

Major (Added Core Sales schemas: Invoice, Quotation, linking CRM to Inventory)

---

Security Impact

Minor (Prepared for Authorization rules blocking invalid deletions)

---

Audit Impact

Major (Outlined hooks for the atomic transaction required upon Invoice Validation)

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

The Sales foundation is established. The exact linkage triggering Stock Reductions and Financial Journals is intentionally mapped as a required TODO inside `SalesService.validate_invoice`. This guarantees the codebase can be built out further without breaking atomic transaction principles.
