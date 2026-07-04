# 10_BUSINESS_ARCHITECTURE.md

Business Architecture (BA)

Version: 1.0

Status: IMMUTABLE

Mandatory

---

# Purpose

This document defines the business architecture of TAJ FROID.

It describes:

• What the company is

• What the company owns

• How information flows

• Which business rules always remain true

• How employees work

• How software should support those workflows

This document is independent from implementation.

The software must follow this document.

This document must never follow the software.

---

# Engineering Principle

Software exists to support business.

Business does not exist to satisfy software.

Whenever a conflict exists,

the software should change,

not the business.

---

# Company Overview

Company

TAJ FROID

Location

Morocco

Primary Activity

Sale

Installation

Maintenance

Repair

After-sales service

of air conditioning systems and related equipment.

Currency

Moroccan Dirham (DH)

Tax

Moroccan VAT

Offline First

Single Company

Single Database

Future multi-PC support

Future cloud synchronization

---

# Business Domains

The company consists of the following domains.

Identity

↓

CRM

↓

Suppliers

↓

Inventory

↓

Purchasing

↓

Sales

↓

Documents

↓

Finance

↓

Expenses

↓

Reporting

↓

Administration

↓

Audit

↓

Settings

Each domain owns its own data.

---

# Domain Ownership

Identity

Owns

Users

Roles

Permissions

Authentication

Settings

---

CRM

Owns

Customers

Customer History

Addresses

Contact Information

Communication

---

Suppliers

Owns

Supplier Records

Purchase History

Supplier Statements

Supplier Contacts

---

Inventory

Owns

Products

Variants

Brands

Categories

Stock

Consumables

Services

Images

---

Purchasing

Owns

Supplier Invoices

Purchases

Stock Entries

Purchase Prices

---

Sales

Owns

Quotations

Invoices

Sales

Customer Orders

Payments

Profit

---

Finance

Owns

Expenses

Balance

Cash Flow

Profit Reports

Financial Journal

---

Documents

Owns

PDF Generation

Printing

Templates

Exports

OCR

---

Administration

Owns

Configuration

Backup

Logs

Maintenance

---

Audit

Owns

Immutable Business History

---

# Business Entities

The following entities exist.

User

Role

Permission

Customer

Supplier

Product

Variant

Brand

Category

Purchase

Sale

Invoice

Quotation

Expense

Payment

Audit Event

Backup

Settings

Every entity has one owner.

No duplicated ownership.

---

# Product

Purpose

Represents anything the company can sell or consume.

Can Be

Physical Product

Consumable

Service

Accessory

Installation Material

Future Equipment

---

Capabilities

Create

Edit

Archive

Restore

Search

Import

Export

Assign Image

Assign Brand

Assign Category

Assign Supplier

Create Variant

Track Stock

Track Purchase Price

Track Sale Price

Generate Audit

Appear in Reports

---

Forbidden

Permanent Delete

Duplicate SKU

Negative Purchase Price

Invalid VAT

---

Relationships

Belongs To

Brand

Category

Supplier

May Have

Variants

Image

Attachments

Purchase History

Sales History

Audit History

---

State Machine

Draft

↓

Active

↓

Archived

---

Invariant

Product ID never changes.

Historical invoices always reference the same product.

Archived products remain visible in history.

---

# Customer

Capabilities

Create

Edit

Archive

Restore

Search

History

Invoices

Quotes

Payments

Communication

---

Invariant

Invoices never lose their customer.

---

# Supplier

Capabilities

Create

Edit

Archive

Statement

History

OCR Mapping

Purchases

---

Invariant

Supplier invoices remain immutable.

---

# Purchase

Purpose

Increase stock.

---

Creates

Stock Movement

Supplier Balance

Audit Event

Financial Journal Entry

---

Invariant

Purchase always increases inventory.

Never decreases it.

---

# Sale

Purpose

Reduce inventory.

Generate revenue.

---

Creates

Invoice

Profit

Stock Reduction

Audit

Customer History

Financial Journal

---

Invariant

Stock never becomes negative.

---

# Invoice

Purpose

Legal financial document.

---

Lifecycle

Draft

↓

Validated

↓

Issued

↓

Paid

↓

Archived

---

Capabilities

Generate PDF

Print

Share

Duplicate

View

Export

Audit

---

Forbidden

Delete

Modify after validation

Reuse invoice number

---

Invariant

Invoice total equals line totals.

Invoice always references customer.

Invoice always belongs to one sale.

---

# Quotation

Lifecycle

Draft

↓

Sent

↓

Accepted

↓

Converted

↓

Archived

---

Can Convert To

Invoice

---

Cannot Convert Back

---

# Expense

Capabilities

Create

Edit

Archive

Categorize

Report

---

Affects

Current Balance

Reports

Cash Flow

Audit

---

Does NOT affect

Gross Profit

---

# Payment

Types

Cash

Cheque

Bank Transfer

TPE

Future Methods

---

Invariant

Paid Amount

≤

Invoice Total

---

# Audit Event

Purpose

Immutable business history.

Never edited.

Never deleted.

Never reused.

Always timestamped.

---

# Business Capabilities

Inventory

Purchase

Sell

Search

Archive

Import

Export

Adjust

Count

Variants

OCR

---

CRM

Customers

History

Communication

Invoices

Quotes

Payments

Reports

---

Finance

Expenses

Profit

Cash Flow

Balance

Journal

Statistics

---

Documents

Generate

Preview

Print

Share

Export

Template

OCR

---

Administration

Users

Permissions

Settings

Backups

Maintenance

Logs

Audit

---

# Business Rules

Every Sale

↓

Creates Invoice

↓

Updates Stock

↓

Updates Customer History

↓

Creates Audit

↓

Updates Reports

↓

Updates Financial Journal

---

Every Purchase

↓

Updates Inventory

↓

Creates Audit

↓

Updates Supplier History

↓

Updates Journal

---

Every Expense

↓

Updates Cash Balance

↓

Creates Audit

↓

Appears in Reports

---

# Global Invariants

Invoices are immutable.

Audit events are immutable.

History is never deleted.

Stock never becomes negative.

Profit is reproducible.

Database is source of truth.

Documents are generated from data.

Every financial operation creates an audit event.

Every critical action is traceable.

IDs never change.

Historical records never lose references.

Backups are always restorable.

---

# User Intent Maps

Administrator

↓

Everything

---

Manager

↓

Dashboard

Reports

Profit

Expenses

Sales

Inventory

Customers

Suppliers

---

Sales Employee

↓

Customer

Quote

Invoice

Payment

Search

Print

---

Inventory Employee

↓

Products

Purchases

Stock

Suppliers

OCR Import

---

Technician

↓

Customer History

Installed Equipment

Products

Previous Visits

Invoices

---

# Reporting

Management requires

Daily Sales

Monthly Sales

Inventory Value

Gross Profit

Net Balance

Expenses

Best Products

Best Customers

Supplier History

Cash Flow

Stock Alerts

Audit Timeline

Employee Activity

---

# Future Extensions

Barcode

QR Code

Warehouse

Multiple Branches

Multiple Companies

Cloud Sync

Mobile App

Customer Portal

Supplier Portal

API

Accounting Integration

AI Assistance

Predictive Analytics

Advanced OCR

Inventory Forecasting

---

# Definition of Success

The software becomes the operational memory of TAJ FROID.

Employees naturally stop using Excel.

Every important business action is recorded exactly once.

Reports are trusted.

Historical information remains accessible.

New employees learn the software quickly.

Managers understand the business at a glance.

The company depends on the software because it increases reliability rather than complexity.

---

# Final Principle

The software does not define TAJ FROID.

TAJ FROID defines the software.

Every feature,

every module,

every database table,

every report,

every workflow,

every line of code

must exist because it faithfully represents a real business process.

If the software ever conflicts with the business,

the software is wrong.

End of 10_BUSINESS_ARCHITECTURE.md