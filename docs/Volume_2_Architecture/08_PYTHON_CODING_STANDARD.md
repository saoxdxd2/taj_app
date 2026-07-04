# 08_PYTHON_CODING_STANDARD.md

# Python Coding Standard (PCS)

Version: 1.0

Status: IMMUTABLE

Mandatory

---

# Purpose

This document defines the mandatory coding standards for all Python code written in this project.

Its purpose is to ensure that every module feels as though it was written by a single experienced engineering team, regardless of when it was created or who created it.

Consistency is a quality feature.

Readable code is maintainable code.

---

# Scope

Applies to:

Core

Modules

Database

UI

Services

Repositories

Utilities

Tests

Scripts

Tools

Generated code should also follow these standards whenever practical.

---

# Engineering Principles

Always prioritize:

Correctness

↓

Readability

↓

Maintainability

↓

Testability

↓

Performance

↓

Micro-optimizations

---

# Python Version

Use only supported Python versions.

Current project target:

Python 3.13+

Do not use deprecated features.

Do not rely on undocumented behavior.

---

# Type Hints

All public functions require type hints.

All return values require type hints.

Prefer explicit types.

Avoid "Any" unless absolutely necessary.

Example

Good

def calculate_profit(cost: float, price: float) -> float:

Bad

def calculate_profit(cost, price):

---

# Docstrings

Every public:

Function

Class

Module

must contain a docstring.

Explain:

Purpose

Arguments

Returns

Raises

Never duplicate obvious code.

Explain intent.

---

# Function Design

Functions should:

Perform one responsibility.

Be short.

Be readable.

Prefer early returns.

Avoid deep nesting.

Avoid hidden side effects.

Aim for approximately:

10–40 lines.

Longer functions require justification.

---

# Class Design

Classes represent cohesive responsibilities.

Avoid "God Classes."

If a class owns unrelated behaviors,

split it.

Large classes are architecture warnings.

---

# File Size

Prefer:

Small modules.

Single responsibility.

Large files are difficult to review.

If a file exceeds roughly 500 lines,

evaluate whether it should be divided.

This is guidance, not a hard limit.

---

# Imports

Standard Library

↓

Third-party Libraries

↓

Project Imports

Never use wildcard imports.

Import only what is required.

Avoid circular imports.

---

# Naming Conventions

Variables

snake_case

Functions

snake_case

Methods

snake_case

Classes

PascalCase

Constants

UPPER_CASE

Private members

_prefix

Modules

snake_case

Packages

snake_case

Names should describe business meaning.

Avoid abbreviations.

---

# Constants

Never use unexplained magic values.

Create named constants.

Bad

if tax == 20:

Good

DEFAULT_MOROCCAN_VAT = 20

---

# Exceptions

Catch only expected exceptions.

Never silently ignore exceptions.

Never use:

except:

Prefer:

except SpecificException:

Always provide meaningful error messages.

---

# Logging

Errors should be logged.

Business actions should be audited.

Never replace audit events with log messages.

Logging is for engineers.

Audit is for business history.

---

# Validation

Validate all external input.

Examples:

User input

OCR

Configuration

Files

Database imports

Network responses

Never assume external data is valid.

---

# Database Access

Database access belongs only inside repositories.

UI should never execute SQL.

Business services should never build SQL strings.

Always use SQLAlchemy ORM or approved abstractions.

---

# Business Logic

Business rules belong only inside services.

Never place calculations inside:

Widgets

Dialogs

Windows

Database models

Repositories

Business knowledge belongs in one place.

---

# Transactions

Critical operations must use transactions.

Never leave partial updates.

Either:

Everything succeeds

or

Everything rolls back.

---

# Configuration

Never hardcode:

Passwords

Secrets

Paths

Keys

Environment-specific values

Use configuration files or environment variables.

---

# Dependencies

Before adding a dependency ask:

Does the standard library already solve this?

Does an existing project dependency already solve this?

Is the dependency actively maintained?

Will it increase long-term maintenance?

---

# Comments

Good comments explain WHY.

Avoid comments that merely describe WHAT.

Bad

Increment i

Good

Increment invoice sequence after successful transaction

---

# TODO Comments

Every TODO must include:

Reason

Owner

(Optional)

Expected future action

Never leave anonymous TODOs.

---

# Code Duplication

Duplicate logic is forbidden.

Shared logic belongs in reusable services.

If similar code appears multiple times,

refactor.

---

# Error Messages

Error messages should:

Explain the problem.

Suggest the cause when possible.

Avoid exposing internal implementation details.

Remain understandable to non-developers when shown in the UI.

---

# Performance

Optimize only after measuring.

Never sacrifice readability for speculative speed.

Prefer algorithmic improvements over micro-optimizations.

---

# Testing

New business logic should include tests.

Critical calculations require tests.

Bug fixes should include regression tests whenever applicable.

---

# Forbidden Practices

Do not:

Use global mutable state.

Mix UI and business logic.

Write SQL in widgets.

Duplicate calculations.

Ignore exceptions.

Use wildcard imports.

Hardcode secrets.

Suppress warnings without justification.

Introduce unnecessary dependencies.

Leave dead code.

Comment out large blocks of code.

---

# Code Review Checklist

Before approval verify:

✓ Clear naming

✓ Small responsibilities

✓ Type hints

✓ Docstrings

✓ Validation

✓ Error handling

✓ Logging

✓ Audit integration

✓ Transactions

✓ Tests

✓ Documentation

✓ No duplicated logic

✓ No architectural violations

---

# Definition of Good Code

Good code should be:

Readable.

Predictable.

Modular.

Consistent.

Documented.

Testable.

Replaceable.

Maintainable.

Professional.

---

# Final Principle

Every Python file should look as though it was written by the same experienced engineering team.

Consistency is more valuable than personal coding style.

Readable code outlives clever code.

Professional software is built one disciplined file at a time.

End of 08_PYTHON_CODING_STANDARD.md