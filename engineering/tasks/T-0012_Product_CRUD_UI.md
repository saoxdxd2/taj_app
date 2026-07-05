# Task Manifest

Task ID: T-0012

Title: Product CRUD UI

Status: Closed

---

Business Objective

Provide a user interface for staff to manage the product catalog (Inventory). This UI will allow the creation, editing, activation, and archiving of products.

---

Engineering Objective

Develop PySide6 UI components for the Inventory module. Build the `ProductDialog` for detailed data entry and the `ProductWidget` for catalog overview and lifecycle control. Ensure seamless integration with the existing `InventoryService`.

---

Dependencies

- T-0006 (Inventory Models & Services)

---

Required Documents

- 12_GUI_STANDARD.md
- 10_BUSINESS_ARCHITECTURE.md

---

Required EDRs

None.

---

Acceptance Criteria

- `ProductDialog` created and wired with PySide6 FormLayout, accommodating strict Decimal handling for prices.
- `ProductWidget` created presenting a tabular view of the catalog.
- UI actions safely mapped to `InventoryService` capabilities.
- `InventoryService` enhanced with `update_product` and read accessors for the GUI.

---

Deliverables

- `src/ui/dialogs/product_dialog.py`
- `src/ui/widgets/product_widget.py`
- Updates to `src/modules/inventory/services.py`

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

Medium

---

Current Phase

Closed

---

Progress

100%

---

Notes

The UI strictly adheres to the PySide6 architecture choice. Session management is cleanly passed to the widgets to keep UI and DB boundaries respected.
