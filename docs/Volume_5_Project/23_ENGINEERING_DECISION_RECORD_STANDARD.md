# 23_ENGINEERING_DECISION_RECORD_STANDARD.md

Engineering Decision Record Standard (EDRS)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

An Engineering Decision Record (EDR) documents significant architectural and engineering decisions made throughout the lifecycle of the project.

Its objective is to preserve engineering knowledge, prevent repeated debates, and explain *why* decisions were made.

Code explains **how**.

Documentation explains **what**.

An EDR explains **why**.

---

# Philosophy

Every important engineering decision represents accumulated reasoning.

Future engineers should understand the rationale without rediscovering it.

An EDR captures that rationale.

---

# When to Create an EDR

Create an Engineering Decision Record whenever a decision:

• Changes the architecture.

• Changes the database.

• Changes security strategy.

• Introduces a major dependency.

• Changes business workflow.

• Affects future extensibility.

• Rejects an alternative approach.

Minor implementation details do not require an EDR.

---

# EDR Identifier

Every record receives a permanent identifier.

Example

EDR-0001

EDR-0002

EDR-0003

Identifiers are never reused.

Deleted records are not renumbered.

---

# EDR Status

Each EDR has one status.

Proposed

Accepted

Superseded

Deprecated

Rejected

Archived

---

# Standard Structure

Every Engineering Decision Record contains:

---

Title

A concise description.

---

Status

Current lifecycle state.

---

Date

Creation date.

---

Context

Describe the problem.

Why was a decision required?

What constraints existed?

---

Decision

Describe the chosen solution.

Be explicit.

Avoid ambiguity.

---

Alternatives Considered

List realistic alternatives.

Summarize advantages and disadvantages.

Explain why they were rejected.

---

Consequences

Positive outcomes.

Trade-offs.

Known limitations.

Future implications.

---

Implementation Notes

Reference affected modules.

Reference documentation.

Reference migration requirements.

Reference related EDRs.

---

Review

Can this decision be revisited?

If yes:

Under what conditions?

---

# Writing Style

An EDR should be:

Objective

Concise

Technical

Evidence-based

Avoid opinions without justification.

---

# Example Topics

SQLite vs PostgreSQL

PySide6 selection

SQLAlchemy selection

Backup strategy

Localization strategy

OCR strategy

Document generation engine

Authentication architecture

Audit architecture

Repository structure

---

# Relationship with PROJECT_MEMORY.md

PROJECT_MEMORY.md stores:

Decision summary.

EDRs store:

Complete reasoning.

Never duplicate full EDRs inside PROJECT_MEMORY.md.

Reference them instead.

---

# Superseding Decisions

Engineering evolves.

If a better solution is adopted:

Do not modify the historical EDR.

Create a new EDR.

Reference the previous one.

Mark the old EDR as:

Superseded.

History remains intact.

---

# Forbidden Practices

Do not create EDRs for:

Variable names.

Minor UI changes.

Small refactoring.

Formatting.

Routine bug fixes.

Focus on durable engineering decisions.

---

# AI Engineering Behavior

Before creating a new EDR, verify:

Does an existing EDR already cover this decision?

Would updating PROJECT_MEMORY.md be sufficient?

Does this decision materially affect future engineering work?

Avoid unnecessary documentation.

---

# Storage

Store EDRs under:

engineering/edr/

Naming convention:

EDR-0001-sqlite-database.md

EDR-0002-pyside6-ui-framework.md

EDR-0003-localization-system.md

File names should clearly communicate the decision.

---

# Engineering Principle

A future engineer should be able to understand every major architectural decision without reading old conversations or commit history.

Engineering knowledge belongs in Engineering Decision Records.

End of 23_ENGINEERING_DECISION_RECORD_STANDARD.md