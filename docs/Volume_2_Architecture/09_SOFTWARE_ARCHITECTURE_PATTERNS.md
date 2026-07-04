# 09_SOFTWARE_ARCHITECTURE_PATTERNS.md

# Software Architecture Patterns (SAP)

Version: 1.0

Status: IMMUTABLE

Mandatory

---

# Purpose

This document defines the architectural patterns that every module in this project must follow.

The objective is consistency.

Every engineer should solve similar problems using similar architecture.

Architecture is not allowed to drift over time.

When multiple implementations are possible,

the patterns defined here always take priority.

---

# Fundamental Principle

The architecture exists to make change easy.

Not to make today's implementation faster.

Good architecture reduces:

Complexity

Coupling

Defects

Technical debt

Future redesign

---

# Architectural Style

The project adopts:

Layered Architecture

combined with

Service-Oriented Business Logic

Repository Pattern

Dependency Injection

Event-Driven Notifications

Domain-Centric Design

NOT

MVC

NOT

Active Record

NOT

Massive Controllers

NOT

God Objects

NOT

Business Logic inside UI

---

# High-Level Layers

Presentation Layer

↓

Application Layer

↓

Domain Layer

↓

Infrastructure Layer

↓

Persistence Layer

↓

Operating System

Dependencies always flow downward.

Never upward.

---

# Layer Responsibilities

## Presentation Layer

Responsible only for:

Displaying data

Collecting user input

Navigation

Dialogs

Tables

Windows

Validation messages

Must NEVER:

Contain business calculations

Contain SQL

Modify database directly

---

## Application Layer

Coordinates workflows.

Calls services.

Combines multiple operations.

Starts transactions.

Creates business commands.

Knows business processes.

Does NOT own business rules.

---

## Domain Layer

Contains:

Business Services

Business Rules

Calculations

Policies

Validation Rules

Profit calculations

VAT calculations

Invoice generation logic

Stock movement rules

This is the heart of the application.

---

## Infrastructure Layer

Contains:

Logging

Configuration

OCR

Printing

PDF generation

Email

Backup

Filesystem

External APIs

Operating system integration

Infrastructure never owns business rules.

---

## Persistence Layer

Responsible only for:

Repositories

ORM

Queries

Transactions

Persistence Mapping

Database sessions

Never perform business decisions.

---

# Repository Pattern

Repositories are the only components allowed to communicate directly with the database.

Responsibilities:

CRUD

Filtering

Searching

Pagination

Transactions

No business calculations.

No business validation.

---

# Service Layer Pattern

Business Services contain:

Business rules

Calculations

Workflows

Validation

Permissions

State transitions

Every important business action begins here.

Examples

InventoryService

SalesService

InvoiceService

SupplierService

OCRService

AuditService

FinanceService

---

# Dependency Injection

Dependencies should be injected.

Never instantiated directly inside business logic.

Good

SalesService(repository)

Bad

SalesService()

↓

Creates Repository()

Dependency Injection improves:

Testing

Maintainability

Reuse

Replacement

---

# Domain Models

Domain models represent business entities.

Examples

Customer

Supplier

Invoice

Quotation

Expense

Product

Category

Payment

User

Audit Event

Settings

They represent business data.

Not UI behavior.

---

# Data Transfer Objects (DTO)

DTOs transport information between layers.

They reduce coupling.

Never expose ORM models directly to UI.

---

# Result Objects

Business operations should return structured results.

Instead of

True

False

Use

Success

Failure

Warnings

Validation Errors

Messages

Affected Records

This improves readability and testing.

---

# Event-Driven Design

Business events should be explicit.

Examples

InvoiceCreated

SaleCompleted

StockUpdated

CustomerCreated

ExpenseAdded

BackupFinished

Events notify other modules.

They do NOT contain business logic.

---

# Validation Pattern

Validation belongs to dedicated validators.

Never duplicate validation.

Never validate inside widgets.

Never validate inside repositories.

Business validation belongs near business logic.

---

# Unit of Work

Multiple related database operations should behave as one transaction.

Examples

Sale

↓

Reduce Stock

Create Invoice

Register Payment

Create Audit

Update Dashboard

Commit

If one fails,

everything rolls back.

---

# State Management

Business objects should have explicit states.

Example

Quotation

Draft

↓

Validated

↓

Accepted

↓

Converted

↓

Archived

Never use unclear Boolean flags.

Use explicit states.

---

# Error Handling Pattern

Errors should travel upward.

Lower layers raise.

Upper layers decide.

UI displays.

Never hide failures.

---

# Factory Pattern

Factories are allowed only when object creation becomes complex.

Avoid unnecessary factories.

Simple constructors are preferred.

---

# Strategy Pattern

Use Strategy when multiple interchangeable algorithms exist.

Examples

OCR Providers

Document Templates

Tax Calculation Variants

Export Formats

Payment Processing

---

# Adapter Pattern

External systems must be wrapped by adapters.

Never let external APIs leak into business logic.

Examples

Windows Printing

OCR

PDF Engine

Future Cloud Sync

---

# Facade Pattern

Large subsystems should expose simple interfaces.

Example

DocumentService

↓

PDF

Print

Preview

Email

Export

One entry point.

Many internal components.

---

# Observer Pattern

Use only for:

UI refresh

Notifications

Dashboard updates

Never replace business workflows with observers.

---

# Command Pattern

Use for business actions.

Examples

Create Invoice

Create Purchase

Register Payment

Delete Product

Commands improve:

Undo

Logging

Audit

Testing

---

# Anti-Patterns (Forbidden)

Business Logic inside UI

Massive MainWindow

God Services

God Repositories

Circular Dependencies

Global Mutable State

Duplicated Business Rules

Hidden Database Access

Utility Classes that do Everything

Copy-Paste Architecture

---

# Folder Responsibility

One folder.

One responsibility.

Examples

services/

repositories/

validators/

events/

dto/

models/

widgets/

dialogs/

Never mix unrelated responsibilities.

---

# Cross Module Communication

Allowed

Application Services

Events

DTOs

Interfaces

Forbidden

Direct database manipulation

Importing internal classes

Calling private methods

Cross-layer shortcuts

---

# Module Independence

Each module should be understandable independently.

Adding a module should require minimal changes elsewhere.

---

# Architectural Stability

Architecture changes are expensive.

Before changing architecture:

Review EDRs.

Review dependencies.

Review future impact.

Architecture should evolve.

Never oscillate.

---

# Architecture Review Checklist

Before approving a module:

✓ Responsibilities clear

✓ No duplicated logic

✓ Dependencies minimal

✓ Business logic centralized

✓ Repository used correctly

✓ Services independent

✓ DTOs appropriate

✓ Events justified

✓ Transactions safe

✓ Testability preserved

---

# Definition of Good Architecture

Good architecture is:

Predictable

Modular

Simple

Composable

Maintainable

Replaceable

Scalable

Documented

Professional

---

# Final Principle

Architecture is the language through which engineers communicate.

Every new module should feel like it naturally belongs to the existing system.

The best architecture is one that future engineers understand immediately without needing to ask why it was designed that way.

End of 09_SOFTWARE_ARCHITECTURE_PATTERNS.md