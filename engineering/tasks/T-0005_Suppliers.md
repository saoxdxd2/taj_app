# Task Manifest

Task ID: T-0005

Title: Suppliers

Status: Closed

---

Business Objective

Establish the Suppliers domain to strictly manage and protect supplier and contact information. Suppliers form the basis for purchases, stock entries, and supplier statements within TAJ FROID.

---

Engineering Objective

Implement the `Supplier` model mapped via SQLAlchemy, enforcing the Soft Delete Policy (archiving) rather than hard deletion, matching the criteria in `10_BUSINESS_ARCHITECTURE.md` and `11_DATABASE_STANDARD.md`.

---

Dependencies

- T-0002 (Database)

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

- `Supplier` model created with ICE number, contact names, and `is_archived` status.
- `SupplierService` created implementing `create_supplier` and `archive_supplier`.
- Soft Delete Policy is enforced for the Supplier lifecycle.

---

Deliverables

- `src/modules/suppliers/models.py`
- `src/modules/suppliers/services.py`

---

Database Impact

Minor (Added Supplier schema)

---

Security Impact

None

---

Audit Impact

Minor (Prepared for audit generation on supplier modification/archival)

---

Documentation Required

Yes (This document and PROJECT_MEMORY.md)

---

Tests Required

None (Unit tests deferred to dedicated QA phase)

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

The Suppliers foundation has been correctly initialized. Soft deletes are built directly into the service lifecycle to prevent historical loss of supplier information.
