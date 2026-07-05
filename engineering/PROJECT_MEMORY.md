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
- **[2026-07-05] Session Summary**: Completed Task T-0011 (Core Integrations). Purged all TODOs from `SalesService` and `PurchasingService` by implementing the `StockLevel` and `StockMovement` systems in `Inventory`. Synchronously hooked `InventoryService`, `FinanceService`, and `AuditService` into the purchasing and sales validation pipelines to enforce the Enterprise Atomic Transaction standard. Updated `T-0011_Core_Integrations.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0012 (Product CRUD UI). Designed and implemented the PySide6 UI views for the Inventory domain. Created `ProductDialog` for creating/editing products via QFormLayout and `ProductWidget` for QTableWidget-driven catalog management. Extended `InventoryService` with secure update and retrieval methods to power the GUI. Updated `T-0012_Product_CRUD_UI.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0013 (CRM UI). Designed and implemented PySide6 UI views for the CRM domain. Created `CustomerDialog` and `CustomerWidget` enabling table-based overview and direct management of customer records. Extended `CRMService` with update methods to bind directly with the GUI logic. Updated `T-0013_CRM_UI.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0014 (Supplier UI). Designed and implemented PySide6 UI views for the Suppliers domain mirroring the CRM pattern. Created `SupplierDialog` and `SupplierWidget` enabling comprehensive record management. Extended `SupplierService` with corresponding read/update accessors for the GUI. Updated `T-0014_Supplier_UI.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0015 (Enterprise Hardening). Enforced strict Authorization and Auditing across all CRUD operations via a newly introduced `RequestContext` and hierarchical `PermissionManager`. Refactored Inventory, CRM, Suppliers, Purchasing, and Sales services. Developed a comprehensive test suite via `pytest` for `InventoryService` that validates Auth, Validation, Rollback, Audit Generation, and Performance. Established `TASK_MANIFEST_TEMPLATE.md` for all future task reporting. Updated `T-0015_Enterprise_Hardening.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0016 (Purchasing UI). Implemented `PurchaseWidget`, `NewPurchaseDialog`, and `PurchaseAddItemDialog` to manage purchasing workflow. UI passes a mock Administrator `RequestContext` down to the hardened services layer. Created split-pane view for lazy-loading Purchase Items connected to a Purchase Order. Updated `T-0016_Purchasing_UI.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0017 (Sales UI). Implemented `SalesWidget`, `NewInvoiceDialog`, and `InvoiceAddItemDialog` mirroring the Purchasing workflow. Users can generate drafts and attach active products with pre-filled default prices and VAT rates. Connecting `validate_invoice` atomically decrements stock safely and registers income via FinanceService. Updated `T-0017_Sales_UI.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Session Summary**: Completed Task T-0018 (Main Application Shell & Authentication). Eradicated all mock `RequestContext` injections across all UI widgets. Built `CurrentSession` singleton and `AuthenticationService` employing Argon2id hashing. Implemented the unified entry point `main.py` launching a `LoginDialog` gateway before presenting the full ERP within `MainWindow` (using a sidebar and `QStackedWidget` for navigation). Updated `T-0018_Main_App_Shell.md` and `PROJECT_MEMORY.md`.
- **[2026-07-05] Engineering Review Sprint (CTO Audit)**: Performed a complete full-repository architecture audit. Identified critical enterprise weaknesses: 1) Transaction boundary logic (`session.commit`) is dangerously located in PySide6 UI widgets instead of a Service Unit of Work. 2) Audit logs are generated manually via `record_event` rather than automated ORM listeners, posing a high risk of forgotten trails. 3) `QTableWidget` poses a long-term memory scalability risk. Suspended feature development. Established a new hard-technical-debt Execution Plan (T-0019 to T-0023). Produced `REVIEW-T0018_CTO_Audit.md`.
