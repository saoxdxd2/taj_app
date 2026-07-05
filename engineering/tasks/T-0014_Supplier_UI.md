# Task Manifest

Task ID: T-0014

Title: Supplier UI

Status: Closed

---

Business Objective

Provide a user interface for staff to manage supplier profiles. This UI allows the creation, editing, and soft-archiving of suppliers used for purchasing.

---

Engineering Objective

Develop PySide6 UI components for the Suppliers module. Build the `SupplierDialog` for data entry and the `SupplierWidget` for the master view. Ensure seamless integration with the existing `SupplierService`.

---

Dependencies

- T-0005 (Suppliers Models & Services)

---

Required Documents

- 12_GUI_STANDARD.md
- 10_BUSINESS_ARCHITECTURE.md

---

Required EDRs

None.

---

Acceptance Criteria

- `SupplierDialog` created with PySide6 FormLayout, allowing management of company name, contact, phone, email, and ICE number.
- `SupplierWidget` created presenting a tabular view of the supplier database.
- UI actions mapped directly to `SupplierService` capabilities.
- `SupplierService` enhanced with `update_supplier` and `get_all_suppliers` accessors.

---

Deliverables

- `src/ui/dialogs/supplier_dialog.py`
- `src/ui/widgets/supplier_widget.py`
- Updates to `src/modules/suppliers/services.py`

---

Database Impact

None

---

Security Impact

None

---

Audit Impact

None

---

Documentation Required

Yes (This document and PROJECT_MEMORY.md)

---

Tests Required

None (GUI unit tests deferred)

---

Estimated Complexity

Low

---

Current Phase

Closed

---

Progress

100%

---

Notes

The UI strictly adheres to the PySide6 architecture choice and mirrors the CRM GUI patterns for consistency.
