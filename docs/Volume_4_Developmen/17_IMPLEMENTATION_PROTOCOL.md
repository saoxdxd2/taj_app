# 17_IMPLEMENTATION_PROTOCOL.md

Implementation Engineering Protocol (IEP)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

This protocol defines the mandatory engineering workflow for implementing any feature within TAJ FROID ERP.

The goal is to maximize correctness, maintainability and long-term consistency.

Implementation is an engineering activity.

Not a code generation activity.

---

# Fundamental Principle

Never begin implementation immediately.

Understanding always precedes coding.

Architecture always precedes implementation.

Implementation always precedes optimization.

Optimization always precedes release.

---

# Engineering Lifecycle

Every task follows the same lifecycle.

Planning

↓

Understanding

↓

Research

↓

Architecture

↓

Design Review

↓

Implementation

↓

Validation

↓

Testing

↓

Documentation

↓

Quality Review

↓

Memory Update

↓

Task Closure

No stage may be skipped without explicit justification.

---

# Phase 1 — Understand

Before writing code the engineering agent shall understand:

Business objective

User objective

Acceptance criteria

Dependencies

Affected modules

Existing architecture

Security implications

Audit implications

Localization requirements

Performance expectations

Unknown requirements must be clarified before implementation.

---

# Phase 2 — Research

Before implementing any capability the engineering agent must determine whether a mature and well-maintained library already solves the problem.

Preference order:

1. Python Standard Library

2. Mature open-source library

3. Existing project component

4. New implementation

Reimplementation requires justification.

---

# Phase 3 — Architecture Review

Before coding verify:

Does this feature fit the current architecture?

Can an existing component be reused?

Can duplication be avoided?

Should a new Engineering Decision Record (EDR) be created?

Would implementing this feature violate any project standard?

If architecture changes are required they must be documented before implementation.

---

# Phase 4 — Design

Produce a lightweight design describing:

Affected modules

Data flow

Business rules

Database impact

User interface impact

Observability impact

Security impact

Testing strategy

Implementation begins only after the design is internally validated.

---

# Phase 5 — Implementation

Implementation should be:

Incremental

Modular

Readable

Testable

Documented

Business logic must remain independent from the UI.

Large implementations should be divided into small verifiable steps.

---

# Phase 6 — Validation

Validate:

Business rules

Data integrity

Permission enforcement

Localization

Audit generation

Logging

Performance expectations

Failure scenarios

Correctness must be verified before testing begins.

---

# Phase 7 — Testing

Execute relevant tests.

Examples:

Unit tests

Integration tests

Database tests

UI tests

Regression tests

Performance checks

Testing scope depends on the impact of the feature.

---

# Phase 8 — Documentation

Update documentation whenever implementation changes:

Architecture

Database

Business rules

API

User documentation

Engineering records

Examples

Documentation and implementation must remain synchronized.

---

# Phase 9 — Quality Review

Perform an engineering self-review.

Verify:

Readability

Maintainability

Security

Performance

Consistency

Reusability

Project standards

If significant weaknesses remain, return to the appropriate earlier phase.

---

# Phase 10 — Project Memory

Update:

PROJECT_MEMORY.md

Relevant EDRs

Task report

Known limitations

Future improvements

Architecture decisions

Temporary reasoning must not be stored.

Only durable knowledge is preserved.

---

# Phase 11 — Task Closure

A task is complete only when:

Implementation finished

Tests pass

Documentation updated

Quality review passed

Project memory updated

Definition of Done satisfied

The task may then be marked Closed.

---

# Implementation Rules

Never mix multiple unrelated features within a single task.

One task

One objective

Large objectives must be decomposed into smaller engineering tasks.

---

# Incremental Development

Prefer:

Small validated improvements

instead of

Large unverified implementations.

Frequent validation reduces engineering risk.

---

# Refactoring

Refactoring is encouraged when it:

Improves readability

Reduces duplication

Simplifies architecture

Improves maintainability

Refactoring must not change observable business behavior unless explicitly intended.

---

# Failure Handling

When implementation fails:

Identify root cause.

Avoid guessing.

Revise the design if necessary.

Repeat the engineering loop.

Failure is treated as feedback rather than completion.

---

# AI Engineering Conduct

The engineering agent must:

Think before coding.

Reason before implementing.

Validate before continuing.

Document before closing.

The objective is not producing code quickly.

The objective is producing software that remains correct for many years.

---

# Engineering Principle

Every completed task should leave the project in a better state than it was before the task began.

End of 17_IMPLEMENTATION_PROTOCOL.md