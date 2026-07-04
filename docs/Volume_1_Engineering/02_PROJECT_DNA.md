# 02_PROJECT_DNA.md

# PROJECT DNA
Project: TAJ FROID Business Management System (TF-BMS)

Version: 1.0

Status: IMMUTABLE

---

# Purpose

This document defines the permanent identity of this project.

It is the project's DNA.

Unlike specifications, tasks, roadmaps, or implementation details, the DNA does not change unless the company itself fundamentally changes.

Every engineering decision must remain consistent with this document.

If implementation conflicts with the DNA, implementation must be changed.

---

# Identity

The software is **not** an ERP clone.

It is **not** an accounting application.

It is **not** a database manager.

It is **not** an invoice generator.

It is the complete operational memory of TAJ FROID.

Every business operation should originate, evolve and remain inside this system.

The application becomes the single trusted source of operational information.

---

# Mission

Replace fragmented manual work (Excel files, scattered documents, manual calculations, duplicated information and repetitive administrative work) with one integrated, reliable and professional desktop application.

The objective is to reduce human error while increasing traceability, productivity and confidence.

---

# Long-Term Vision

The application should remain usable and maintainable after at least ten years of daily use.

Future developers should understand the architecture without rewriting it.

The software should grow through evolution rather than redesign.

The system must be capable of handling many years of accumulated business data without requiring architectural replacement.

---

# Business Context

Company

TAJ FROID

Country

Morocco

Currency

Moroccan Dirham (DH)

Primary Activity

Sale, installation and maintenance of air-conditioning equipment.

Company Size

Approximately 11 employees.

Deployment

Single company.

Single primary workstation.

Offline-first.

Future synchronization may be added without redesign.

---

# Business Philosophy

The software adapts to the business.

The business never adapts to software limitations.

If a workflow feels unnatural to employees, redesign the software rather than forcing inefficient processes.

The software exists to simplify work.

Never to create additional work.

---

# Single Source of Truth

The database is the only authoritative source of information.

Generated documents never become the source of truth.

Invoices

Quotations

PDFs

Prints

Reports

are views generated from the database.

If a document differs from the database,

the database is always correct.

---

# Workflow Philosophy

The application is workflow-driven.

Not page-driven.

Employees perform business operations.

The software performs administrative operations.

Example:

Employee:

Complete Sale

Software:

Generate invoice

Update inventory

Calculate VAT

Calculate profit

Update customer history

Update accounting journal

Generate audit events

Refresh dashboard

The employee should think about business,

never software.

---

# Design Philosophy

The interface must communicate:

Professionalism

Stability

Precision

Trust

Efficiency

The goal is not visual beauty.

The goal is confidence.

Every screen should feel like software that professionals use every day.

---

# User Experience Philosophy

The software should feel:

Fast.

Predictable.

Compact.

Reliable.

Consistent.

The user should rarely wonder where to click next.

The interface should become familiar through repetition and consistency.

---

# Enterprise Feel

The application must never resemble:

A university project.

A prototype.

A dashboard template.

A Bootstrap admin panel.

A generated desktop application.

Instead it should resemble professional Windows desktop software.

Information density is preferred over excessive whitespace.

Tables are first-class components.

Keyboard shortcuts are expected.

Professional typography is mandatory.

Animations are minimal.

---

# Engineering Philosophy

Every implementation must satisfy:

Business correctness.

Data integrity.

Security.

Maintainability.

Performance.

Professional code quality.

Implementation convenience is never a valid justification for poor engineering.

---

# Simplicity

Complexity must only exist where business complexity genuinely exists.

Artificial complexity is forbidden.

Simple software is easier to trust.

---

# Data Philosophy

Business data is permanent.

Historical records are valuable.

Invoices are never deleted.

Audit events are never deleted.

Products are archived.

Customers are archived.

Suppliers are archived.

Historical information remains available forever.

---

# Audit Philosophy

Every important business action creates an immutable audit event.

Audit information is considered business data.

The audit system must allow reconstruction of every significant business event.

No critical operation may occur silently.

---

# Security Philosophy

Protect company data.

Protect user accounts.

Protect business history.

Protect backups.

Security should be practical rather than excessive.

The application is intended for trusted employees, but mistakes and misuse must still be prevented.

---

# Performance Philosophy

Performance is a feature.

The user should never wait unnecessarily.

Slow operations should provide visible progress.

The interface must remain responsive.

Performance optimizations should never compromise correctness.

---

# Reliability Philosophy

The application must behave predictably.

Unexpected behavior is considered a defect.

Partial operations are unacceptable.

Critical business operations must be transactional.

Either everything succeeds,

or nothing changes.

---

# Maintainability Philosophy

The project should be understandable years later.

Readable architecture is preferred over clever architecture.

Every module should have one clear responsibility.

Future developers should extend the system rather than rewrite it.

---

# Reuse Philosophy

Never reinvent mature, reliable solutions.

Before implementing functionality,

evaluate existing Python libraries.

Reuse mature components whenever appropriate.

Custom implementation is justified only when:

No mature library exists.

The library cannot satisfy business requirements.

Long-term maintenance clearly benefits.

---

# OCR Philosophy

Artificial intelligence is not the default solution.

Deterministic automation is preferred whenever document structure is predictable.

Supplier invoice OCR should use dedicated parsers.

AI should only be considered when deterministic methods become insufficient.

Accuracy is more important than novelty.

---

# Document Philosophy

Documents are outputs.

Not inputs.

The user records business operations.

The application generates documents automatically.

Documents should never require manual formatting.

Every document should originate from the same document generation engine.

---

# Backup Philosophy

Data loss is unacceptable.

The application should automatically create backups.

Recovery must be simple.

Backups should be versioned.

Backups should be restorable without developer intervention.

Future cloud synchronization must remain optional.

---

# Search Philosophy

Searching should feel immediate.

Partial names.

Models.

Brands.

Categories.

Related records.

Historical records.

Everything should be discoverable through a unified search experience.

The user should never need to remember where information was originally stored.

---

# Future Growth

The architecture should anticipate future expansion without implementing unnecessary functionality today.

Examples:

Barcode support.

Serial numbers.

Multiple workstations.

Cloud synchronization.

OCR providers.

Additional document templates.

Additional suppliers.

Mobile companion applications.

These possibilities should influence architecture but not create unnecessary implementation.

---

# Definition of Success

The project succeeds when employees naturally stop using Excel for daily operations.

Users trust the software.

Business information becomes easier to find than paper documents.

New employees learn the software quickly.

Management can understand the state of the business from the dashboard.

The application becomes an indispensable part of the company.

---

# Definition of Failure

The project has failed if:

Employees return to Excel.

Users avoid certain features.

Business data becomes inconsistent.

Architecture requires repeated redesign.

Users no longer trust the software.

Performance degrades significantly over time.

The software becomes difficult to maintain.

---

# Guiding Question

Every engineering decision should answer:

"Does this move TAJ FROID closer to having one reliable, professional and long-lasting digital operational memory?"

If the answer is not clearly "Yes",

the decision should be reconsidered.

---

# Final Principle

This software is not merely a desktop application.

It is the digital representation of how TAJ FROID operates.

Every feature exists to support a real business activity.

Every workflow exists to reduce unnecessary work.

Every line of code exists because it improves the long-term reliability, maintainability and usefulness of the system.

End of 02_PROJECT_DNA.md