# 18_PROJECT_MEMORY.md

Project Memory Standard (PMS)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

PROJECT_MEMORY.md is the persistent engineering memory of the project.

It stores durable engineering knowledge that must survive across development sessions.

Its objective is to preserve architectural consistency while minimizing unnecessary context consumption.

It is not a conversation log.

It is not a development diary.

It is the long-term memory of the project.

---

# Philosophy

Human engineers do not remember every conversation.

They remember:

Architecture

Business rules

Important decisions

Lessons learned

The engineering agent must behave similarly.

Temporary reasoning is discarded.

Long-term knowledge is preserved.

---

# Primary Objectives

Maintain continuity across sessions.

Reduce repeated reasoning.

Prevent architectural drift.

Avoid reintroducing rejected solutions.

Provide a concise summary of the current state of the project.

---

# Memory Principles

Store knowledge.

Not thoughts.

Store conclusions.

Not discussions.

Store decisions.

Not debates.

Store architecture.

Not implementation details.

---

# Memory Categories

PROJECT_MEMORY.md is divided into the following sections.

---

## 1. Project Identity

Project name

Current version

Current development phase

Primary objectives

Last updated

---

## 2. Architecture Summary

Current architecture

Major modules

Database engine

ORM

GUI framework

Dependency injection

Logging

Audit

Localization

Document generation

OCR

Printing

Backup strategy

---

## 3. Engineering Decisions

Reference accepted Engineering Decision Records (EDRs).

Each entry includes:

Decision

Reason

Reference

Status

---

## 4. Business Rules

Only stable business rules belong here.

Examples:

VAT policy

Quotation workflow

Invoice numbering

Inventory principles

Expense calculation

Role definitions

---

## 5. Database Summary

Current schema version

Migration status

Critical constraints

Naming conventions

Important relationships

---

## 6. Reusable Components

List reusable services.

Examples:

Audit Service

Document Generator

Localization Manager

Backup Manager

Permission Manager

OCR Import Service

---

## 7. Active Modules

Current implementation status.

Example

Products

Completed

Customers

In Progress

Suppliers

Planned

Sales

Planned

---

## 8. Known Technical Debt

Describe:

Problem

Reason

Impact

Priority

Possible solution

---

## 9. Known Risks

Current architectural risks.

Future migration concerns.

Performance concerns.

Security concerns.

---

## 10. Rejected Decisions

Record important rejected ideas.

Each rejection includes:

Idea

Reason

Date

Replacement (if any)

This prevents repeating previous discussions.

---

## 11. Future Roadmap

Features intentionally postponed.

Future architecture.

Planned improvements.

Version 2 ideas.

---

## 12. Lessons Learned

Only durable engineering lessons.

Examples:

Avoid coupling business logic to UI.

Use transactions for inventory updates.

OCR requires supplier-specific templates.

---

## 13. Session Summary

At the end of every completed engineering session append a concise summary.

Each summary contains:

Completed tasks

Major decisions

Updated documents

Open issues

Recommended next task

Limit summaries to essential information.

---

# Update Rules

Update PROJECT_MEMORY.md only when durable project knowledge changes.

Do not update it after every code edit.

Minor implementation details should not appear.

---

# Size Management

PROJECT_MEMORY.md must remain concise.

Target length:

Under 15 pages.

If it grows excessively:

Summarize.

Merge redundant entries.

Archive obsolete information.

---

# Forbidden Content

Do not store:

Temporary reasoning.

Internal chain of thought.

Exploratory ideas.

Implementation experiments.

Verbose meeting notes.

Scratch work.

These belong only to the current engineering session.

---

# Relationship with TASK_MEMORY.md

TASK_MEMORY.md

Temporary.

Task-specific.

Deleted or reset after task completion.

PROJECT_MEMORY.md

Persistent.

Project-wide.

Maintained throughout the project's lifetime.

---

# Relationship with EDRs

PROJECT_MEMORY.md summarizes decisions.

EDRs explain decisions.

Never duplicate complete EDR content.

Reference it instead.

---

# Relationship with Documentation

Documentation explains the system.

PROJECT_MEMORY.md explains the current state of the project.

These have different purposes.

---

# Engineering Principle

PROJECT_MEMORY.md should allow a new senior engineer to understand the current state of the ERP in minutes rather than hours.

If the document becomes difficult to maintain or understand, it should be simplified.

End of 18_PROJECT_MEMORY.md