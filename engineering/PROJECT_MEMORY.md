# PROJECT_MEMORY.md

Persistent Engineering Memory

This document stores long-term engineering knowledge.

Never delete information.

Instead archive obsolete information.

This file should remain concise.

---

# Current Version

Version:

Current Phase:

Last Updated:

---

# Current Architecture

Architecture Version:

Database:

ORM:

GUI:

Dependency Injection:

Document Engine:

Logging:

Audit:

Localization:

Theme:

OCR:

Printing:

Testing:

---

# Engineering Decisions

List every accepted Engineering Decision Record.

Example

EDR-0001

SQLite selected.

Reason:

Single-PC architecture.

Future migration supported.

---

# Chosen Libraries

PySide6

SQLAlchemy

Alembic

Loguru

WeasyPrint

OpenCV

RapidFuzz

etc.

---

# Completed Tasks

T-0001

Foundation

Completed

---

T-0002

Authentication

Completed

---

# Active Tasks

...

---

# Future Tasks

...

---

# Known Technical Debt

None

or

Describe debt.

Reason.

Priority.

---

# Known Risks

...

---

# Rejected Ideas

Keep important rejected ideas.

Explain why.

Never reconsider without evidence.

---

# Performance Notes

...

---

# Database Notes

...

---

# Security Notes

...

---

# UI Notes

...

---

# Future Extensions

Barcode

Warehouse

Cloud Sync

REST API

Mobile App

AI Assistant

etc.

---

# Session Summary

Append a short summary after each completed engineering session.

- **[2026-07-05] Session Summary**: Completed Task T-0001 (Foundation). Executed exactly one task to strictly initialize the repository directory structure according to `20_DIRECTORY_STRUCTURE.md`. Created all essential module, layer, and resource directories. Updated `TASK_MEMORY.md` (and appropriately archived in `T-0001_Foundation.md`).
- **[2026-07-05] Session Summary**: Completed Task T-0002 (Database). Initialized SQLAlchemy 2.x infrastructure with `BaseModel` (including automatic `created_at`, `updated_at`, and `id` audit fields) and SQLite session manager enforcing foreign keys. Updated `T-0002_Database.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0003 (Authentication). Implemented `User` model and `Role` enum in `src/modules/authentication/models.py`. Implemented `AuthenticationService` using `argon2-cffi` for secure password hashing and verification in compliance with `15_SECURITY_STANDARD.md`. Updated `T-0003_Authentication.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0004 (CRM). Engineered `Customer` and `Address` data models defining proper SQLAlchemy foreign-key relationships. Developed `CRMService` to implement customer creation and strictly enforce the Soft Delete (archival) Policy. Updated `T-0004_CRM.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0005 (Suppliers). Engineered `Supplier` data model and established `SupplierService` to handle creation and soft archival matching the core business requirements. Updated `T-0005_Suppliers.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0006 (Inventory). Engineered `Product`, `Brand`, and `Category` models, incorporating the strict Draft/Active/Archived state machine. Enforced the `Decimal` standard for monetary values to prevent floating-point loss. Developed `InventoryService`. Updated `T-0006_Inventory.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0007 (Purchasing). Engineered `Purchase` and `PurchaseItem` models. Built `PurchasingService` establishing the Draft -> Validated state machine and enforcing the framework for atomic, cross-domain transactions (Stock, Finance, Audit) as defined in the Business Architecture. Updated `T-0007_Purchasing.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0008 (Sales). Engineered `Invoice`, `Quotation`, and their respective Item data models. Built `SalesService` mapping the Draft -> Validated lifecycle, enforcing strict immutability post-validation and scaffolding hooks for atomic transactions into inventory and finance. Updated `T-0008_Sales.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0009 (Finance). Engineered the immutable `FinancialJournalEntry` model alongside `Expense`. Built `FinanceService` applying insert-only architectural rules ensuring transaction history can only be properly reversed via counter-entries, never overwritten. Updated `T-0009_Finance.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0010 (Audit). Engineered the `AuditEvent` model using JSON fields to safely record historical state (`before_values`/`after_values`). Established the strictly append-only `AuditService` to permanently log critical business and security operations across all domains. Updated `T-0010_Audit.md` and `PROJECT_MEMORY.md`.
