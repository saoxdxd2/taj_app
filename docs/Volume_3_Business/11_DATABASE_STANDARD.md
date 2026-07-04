# 11_DATABASE_STANDARD.md

# Database Engineering Standard (DES)

Version: 1.0

Status: IMMUTABLE

Mandatory

---

# Purpose

This document defines every rule governing the design, implementation,
maintenance and evolution of the TAJ FROID database.

The database is the single source of truth for the company.

Every report,
every invoice,
every quotation,
every dashboard,
every calculation,
every audit record,

originates from the database.

A mistake in the database propagates everywhere.

Therefore database engineering receives the highest engineering discipline.

---

# Fundamental Principle

The database stores business truth.

The application displays that truth.

Documents represent that truth.

Nothing else owns business data.

---

# Database Philosophy

The database is designed for:

Correctness

↓

Integrity

↓

Longevity

↓

Maintainability

↓

Performance

↓

Convenience

Never sacrifice integrity for convenience.

---

# Technology

Approved Database

SQLite

ORM

SQLAlchemy 2.x

Migration Tool

Alembic

Future migration to PostgreSQL must remain possible.

Vendor lock-in should be minimized.

---

# Engineering Objectives

The database must provide:

Reliability

Consistency

Atomicity

Traceability

Recoverability

Scalability

Maintainability

Predictability

---

# Single Source of Truth

The database is authoritative.

Never trust:

Excel

PDF

OCR

User Input

CSV

Imported Files

Generated Reports

All imported data must be validated before persistence.

---

# Normalization

Normalize until business complexity becomes unreasonable.

Avoid duplicated data.

Avoid hidden dependencies.

Avoid inconsistent updates.

Denormalization is permitted only when:

Performance is measured.

Benefits outweigh complexity.

Decision documented in an EDR.

---

# Entity Ownership

Every table has one owner.

Examples

Products

↓

Inventory Domain

Invoices

↓

Sales Domain

Customers

↓

CRM Domain

Audit

↓

Audit Domain

Ownership never overlaps.

---

# Naming Convention

Tables

snake_case

Columns

snake_case

Primary Keys

id

Foreign Keys

entity_id

Boolean Fields

is_active

is_deleted

is_archived

Timestamps

created_at

updated_at

archived_at

deleted_at

---

# Primary Keys

Every table has one immutable primary key.

IDs never change.

IDs are never reused.

Business identifiers remain separate.

Example

invoice_number

≠

Primary Key

---

# Foreign Keys

Use explicit foreign keys.

Do not store relationships manually.

Database integrity must enforce relationships.

---

# Constraints

Use database constraints whenever possible.

Examples

UNIQUE

CHECK

FOREIGN KEY

NOT NULL

Business rules should be enforced at both:

Application Layer

Database Layer (where appropriate)

---

# Transactions

Critical business operations are atomic.

Example

Sale

↓

Create Invoice

↓

Reduce Stock

↓

Create Journal Entry

↓

Create Audit

↓

Commit

If any step fails

↓

Rollback Everything

Partial business operations are forbidden.

---

# Soft Delete Policy

Business entities are archived.

Not deleted.

Examples

Products

Customers

Suppliers

Users

Categories

Brands

Deletion exists only for temporary or non-business data.

---

# Immutable Records

Never modify:

Invoices

Audit Events

Historical Journal Entries

Completed Financial Records

Instead

Cancel

Reverse

Archive

Never rewrite history.

---

# Historical Integrity

Relationships must remain valid forever.

Old invoices must still reference:

Customer

Products

VAT

Prices

Even if those entities become archived.

Historical reports must always be reproducible.

---

# Monetary Values

Never use floating-point numbers for money.

Use Decimal.

Store monetary precision consistently.

All financial calculations must be deterministic.

---

# Dates and Time

Store timestamps in UTC internally.

Display according to user locale if needed.

Every business entity should include:

created_at

updated_at

Every financial event also includes:

effective_date

---

# Indexing Strategy

Index:

Foreign Keys

Invoice Numbers

Customer Search

Supplier Search

Product Model

Product Name

Created Date

Business Search Fields

Avoid unnecessary indexes.

Indexes increase write cost.

---

# Search Philosophy

Searching must remain fast.

Support:

Partial text

Model

Brand

Category

Invoice Number

Customer Name

Supplier Name

Product Name

Future full-text search should remain possible.

---

# Migrations

All schema changes require Alembic migrations.

Never manually modify production schemas.

Every migration must be reversible whenever practical.

---

# Backup Compatibility

Schema evolution must never invalidate backups.

Older backups should remain restorable.

Migration paths must be documented.

---

# Audit Integration

Every critical transaction creates:

Audit Event

Timestamp

User

Action

Entity

Before Values

After Values

Correlation ID

No silent business changes.

---

# Performance

Measure first.

Optimize second.

Expected performance goals:

Application startup

< 3 seconds

Product search

< 200 ms

Invoice generation

< 500 ms

Dashboard loading

< 2 seconds

These are targets, not guarantees.

---

# Future Compatibility

The schema should anticipate:

Barcode

Multiple Warehouses

Multiple Branches

Cloud Sync

PostgreSQL

REST API

Mobile App

without requiring redesign.

---

# Data Validation

Validation occurs in three layers:

1. UI

↓

2. Business Services

↓

3. Database Constraints

Never rely on only one layer.

---

# Security

Never store plaintext passwords.

Never expose internal IDs unnecessarily.

Sensitive configuration belongs outside the database where appropriate.

---

# Database Review Checklist

Before approving a schema:

✓ Naming consistent

✓ Relationships correct

✓ Constraints defined

✓ Transactions safe

✓ Monetary precision correct

✓ Historical integrity preserved

✓ Indexes appropriate

✓ Migration created

✓ Backup compatibility maintained

✓ Audit supported

✓ Future growth considered

---

# Forbidden Practices

Do not:

Delete historical financial records.

Use floating-point money.

Duplicate business data.

Bypass repositories.

Modify production schema manually.

Store business logic in SQL triggers without justification.

Break referential integrity.

Reuse primary keys.

Use nullable fields without reason.

---

# Definition of Database Quality

A professional database is:

Correct

Predictable

Consistent

Recoverable

Auditable

Maintainable

Fast

Well documented

Easy to migrate

Difficult to corrupt

---

# Final Principle

The database is the company's memory.

Applications can be rewritten.

Interfaces can change.

Reports can evolve.

But the database preserves the history of the business.

Design it as though it must still be trusted ten years from today.

End of 11_DATABASE_STANDARD.md