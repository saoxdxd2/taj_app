# 21_TASK_MANAGEMENT_STANDARD.md

Enterprise Task Management Standard (ETMS)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

This standard defines how engineering work is organized, tracked, executed and completed.

The objective is to make every task:

• Predictable

• Independent

• Traceable

• Reviewable

• Recoverable

A project succeeds through hundreds of well-executed tasks rather than a few massive implementations.

---

# Engineering Philosophy

Never think in terms of files.

Think in terms of engineering objectives.

Every task should solve exactly one business or technical objective.

---

# Task Granularity

Tasks must remain small enough to be:

Understood quickly.

Reviewed easily.

Tested independently.

Reverted safely.

Merged confidently.

---

Good Example

Implement Product Repository

Bad Example

Implement Inventory Module

---

# Task Categories

Business Feature

Technical Infrastructure

Architecture

Database

Security

Testing

Documentation

Performance

Refactoring

Bug Fix

Maintenance

Research

Each task belongs to exactly one primary category.

---

# Task Lifecycle

Every task follows the same lifecycle.

Backlog

↓

Ready

↓

In Progress

↓

Engineering Review

↓

Testing

↓

Documentation Updated

↓

Definition of Done

↓

Closed

↓

Archived

Tasks never skip states.

---

# Task Structure

Each task contains:

Unique Identifier

Title

Objective

Business Value

Scope

Dependencies

Acceptance Criteria

Risk Level

Estimated Complexity

Affected Modules

Required Documentation

Expected Tests

---

# Task Naming

Good

TASK-0023

Implement Product Repository

Bad

Inventory Stuff

Fix Everything

Database Changes

Names must clearly describe the objective.

---

# Dependencies

Tasks should explicitly declare:

Depends On

Blocks

Related Tasks

Parallel Tasks

Engineering agents must respect dependency order.

---

# Task Priority

Critical

High

Normal

Low

Priority reflects business impact rather than implementation difficulty.

---

# Complexity Levels

L0 — Configuration

No source code modifications.

L1 — Small Change

One component.

Minimal risk.

L2 — Feature

Several components.

Existing architecture.

L3 — Module

New module.

Database changes.

Cross-service interactions.

L4 — Core System

Touches multiple business domains.

High architectural impact.

L5 — Architectural Evolution

Changes project-wide engineering decisions.

Requires EDR.

---

# Acceptance Criteria

Acceptance criteria must be:

Observable.

Objective.

Testable.

Business-oriented.

Avoid vague wording such as:

"It should work."

Instead use:

"A new customer can be created, edited, searched and archived."

---

# Parallel Development

Independent tasks may execute in parallel.

Tasks modifying the same architecture should remain sequential.

Correctness takes priority over speed.

---

# Scope Control

A task must never silently grow.

If new requirements appear:

Evaluate.

Document.

Create a new task if necessary.

Avoid feature creep.

---

# Task Reports

Every completed task generates a short engineering report.

Include:

Summary

Files Modified

Architecture Impact

Database Impact

Tests Executed

Documentation Updated

Known Limitations

Future Improvements

The report must remain concise.

---

# Interrupted Tasks

If work stops before completion:

Record current progress.

Record blockers.

Record next recommended action.

Update TASK_MEMORY.md.

The next engineering session should continue without rediscovering previous work.

---

# Engineering Review

Before closing:

Verify acceptance criteria.

Verify standards compliance.

Verify documentation.

Verify testing.

Verify project memory.

Verify Definition of Done.

---

# Archived Tasks

Closed tasks become immutable historical records.

History must remain available for future engineering analysis.

Archived tasks must never become active again.

Instead:

Create a new task referencing the archived one.

---

# Engineering Metrics

The objective is NOT maximizing completed tasks.

The objective is maximizing completed quality work.

Metrics should emphasize:

Predictability

Stability

Quality

Maintainability

Not task count.

---

# AI Engineering Behavior

The engineering agent must resist:

Combining unrelated work.

Skipping documentation.

Skipping testing.

Skipping architecture review.

Skipping project memory updates.

Engineering discipline always takes precedence over speed.

---

# Final Principle

The project advances one well-engineered task at a time.

Many small successes build a reliable ERP.

Large uncontrolled implementations build technical debt.

End of 21_TASK_MANAGEMENT_STANDARD.md