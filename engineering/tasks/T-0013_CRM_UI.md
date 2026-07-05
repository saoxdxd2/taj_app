# Task Manifest

Task ID: T-0013

Title: CRM UI

Status: Closed

---

Business Objective

Provide a user interface for staff to manage customer profiles (CRM). This UI will allow the creation, editing, and soft-archiving of customers.

---

Engineering Objective

Develop PySide6 UI components for the CRM module. Build the `CustomerDialog` for data entry and the `CustomerWidget` for CRM overview. Ensure seamless integration with the existing `CRMService`.

---

Dependencies

- T-0004 (CRM Models & Services)

---

Required Documents

- 12_GUI_STANDARD.md
- 10_BUSINESS_ARCHITECTURE.md

---

Required EDRs

None.

---

Acceptance Criteria

- `CustomerDialog` created with PySide6 FormLayout, allowing management of company name, contact, phone, email, and ICE number.
- `CustomerWidget` created presenting a tabular view of the customer database.
- UI actions mapped to `CRMService` capabilities.
- `CRMService` enhanced with `update_customer` and read accessors for the GUI.

---

Deliverables

- `src/ui/dialogs/customer_dialog.py`
- `src/ui/widgets/customer_widget.py`
- Updates to `src/modules/crm/services.py`

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

The UI strictly adheres to the PySide6 architecture choice.
