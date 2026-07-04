# 19_DEFINITION_OF_DONE.md

Definition of Done (DoD)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

This document defines the minimum conditions required before any engineering task may be considered complete.

Completion is determined by engineering quality rather than implementation effort.

A task is not finished because code exists.

A task is finished because it satisfies all applicable engineering standards.

---

# Philosophy

Working software is necessary.

Reliable software is required.

Maintainable software is expected.

Production-ready software is the objective.

---

# General Rule

A task may only be marked **Closed** after every applicable requirement in this document has been satisfied.

If any mandatory requirement remains incomplete, the task returns to the implementation lifecycle.

---

# Functional Completion

The implemented feature:

✓ Meets the original business objective.

✓ Meets the engineering objective.

✓ Satisfies all acceptance criteria.

✓ Produces the expected results.

✓ Handles expected inputs correctly.

✓ Handles expected failure conditions gracefully.

---

# Architecture

The implementation:

✓ Respects the approved architecture.

✓ Does not introduce unnecessary coupling.

✓ Reuses existing components whenever appropriate.

✓ Avoids duplicated business logic.

✓ Does not violate established Engineering Decision Records (EDRs).

---

# Code Quality

The implementation:

✓ Is readable.

✓ Is maintainable.

✓ Uses consistent naming.

✓ Avoids unnecessary complexity.

✓ Removes dead code.

✓ Avoids premature optimization.

✓ Includes meaningful comments where necessary.

---

# Business Logic

Business rules:

✓ Are implemented correctly.

✓ Remain independent of the user interface.

✓ Are validated.

✓ Preserve data integrity.

---

# Database

Database changes:

✓ Are normalized.

✓ Preserve referential integrity.

✓ Include migrations when required.

✓ Execute within transactions where appropriate.

✓ Do not corrupt existing data.

---

# Security

Security review confirms:

✓ Permission checks exist.

✓ Authentication rules are respected.

✓ Sensitive information is protected.

✓ User input is validated.

✓ Secrets are not hardcoded.

---

# Observability

The feature:

✓ Generates required audit events.

✓ Produces meaningful logs.

✓ Integrates with the Business Journal where applicable.

✓ Supports troubleshooting.

---

# Localization

The feature:

✓ Contains no hardcoded user-facing text.

✓ Uses localization keys.

✓ Supports all currently available languages.

---

# User Interface

The interface:

✓ Matches the Design System.

✓ Uses standard navigation patterns.

✓ Is visually consistent.

✓ Handles errors clearly.

✓ Supports keyboard navigation where applicable.

---

# Performance

The implementation:

✓ Meets performance expectations.

✓ Avoids unnecessary database queries.

✓ Avoids blocking the user interface.

✓ Uses appropriate algorithms and data structures.

---

# Testing

Applicable tests:

✓ Exist.

✓ Pass successfully.

✓ Cover critical business behavior.

✓ Include regression tests for resolved defects when practical.

---

# Documentation

Relevant documentation:

✓ Has been updated.

✓ Matches the implementation.

✓ Includes new architectural decisions where necessary.

✓ References related Engineering Decision Records.

---

# Project Memory

PROJECT_MEMORY.md:

✓ Reflects durable changes.

✓ Includes important engineering decisions.

✓ Omits temporary reasoning.

---

# Task Memory

TASK_MEMORY.md:

✓ Has been updated during implementation.

✓ Has been summarized.

✓ Is ready to be archived or reset.

---

# Engineering Review

The implementation has been reviewed for:

✓ Simplicity.

✓ Maintainability.

✓ Consistency.

✓ Future extensibility.

✓ Compliance with project standards.

---

# Release Readiness

The feature:

✓ Can safely be merged into the main project.

✓ Does not knowingly introduce critical defects.

✓ Does not reduce overall software quality.

---

# Explicitly Not Done

A task is NOT complete merely because:

• The code compiles.

• The application starts.

• The feature appears to work.

• The happy path succeeds.

• The UI looks correct.

Engineering quality determines completion.

Not visible progress.

---

# Final Engineering Principle

Every completed task should leave the project more reliable, more maintainable, and easier to extend than it was before the task began.

If future engineers benefit from today's work, the task is truly complete.

End of 19_DEFINITION_OF_DONE.md