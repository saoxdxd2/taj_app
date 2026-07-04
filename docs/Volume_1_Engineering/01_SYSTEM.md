# 01_SYSTEM.md

# Software Engineering Constitution (SEC)

Version: 1.0

Status: IMMUTABLE

This document defines the engineering operating system used for every software project.

It does not describe the application.

It describes HOW software must be engineered.

Every future document derives from this one.

---

# 1. Mission

Software engineering is not programming.

Programming is only one activity inside software engineering.

The objective of this system is to consistently produce production-grade software through disciplined engineering rather than code generation.

Every decision shall prioritize long-term quality over short-term implementation speed.

The goal is not to write code.

The goal is to engineer systems.

---

# 2. Core Philosophy

This engineering system is built upon one principle:

> Correct engineering naturally produces correct software.

Poor engineering eventually produces technical debt.

Therefore every engineering decision must improve one or more of the following:

• Correctness

• Reliability

• Maintainability

• Security

• Scalability

• Performance

• Simplicity

• Documentation

• Testability

If none improve, reconsider the decision.

---

# 3. Engineering Pyramid

Every project follows this hierarchy.

Implementation never starts at the bottom.

                    Vision
                      │
                Business Model
                      │
               Business Domains
                      │
                Architecture
                      │
                 Workflows
                      │
                Database Model
                      │
               Module Contracts
                      │
                  UI Design
                      │
             Implementation Plan
                      │
                     Code
                      │
                    Tests
                      │
              Documentation

Each layer depends only on layers above it.

Lower layers must never redefine higher layers.

---

# 4. Engineering Cycle

Every task follows the same recursive engineering cycle.

Understand

↓

Research

↓

Analyze

↓

Design

↓

Critique

↓

Improve

↓

Validate

↓

Implement

↓

Review

↓

Refactor

↓

Test

↓

Document

↓

Evaluate

↓

Repeat if necessary

Engineering is iterative.

Implementation is only one iteration.

---

# 5. Recursive Engineering Protocol

The AI must continuously evaluate whether the current solution is the best reasonable solution.

The first working implementation is never automatically considered complete.

Before continuing ask:

Can it become simpler?

Can complexity be reduced?

Can existing code be reused?

Can architecture improve?

Can readability improve?

Can reliability improve?

Can testing improve?

Can documentation improve?

If the answer is yes,

repeat another engineering cycle.

---

# 6. Decision Priority

Every engineering decision follows this priority.

1. Business Correctness

2. Data Integrity

3. Security

4. Reliability

5. Architecture

6. Maintainability

7. Testability

8. Simplicity

9. Performance

10. User Experience

11. Developer Convenience

A lower priority must never compromise a higher priority.

---

# 7. Engineering Layers

The project is divided into independent engineering layers.

Business Layer

Defines what the company does.

Architecture Layer

Defines system organization.

Domain Layer

Defines business modules.

Workflow Layer

Defines business operations.

Data Layer

Defines persistence.

Service Layer

Contains business logic.

Infrastructure Layer

Provides technical services.

Presentation Layer

Displays information.

Testing Layer

Verifies behavior.

Documentation Layer

Explains the system.

Each layer has a single responsibility.

---

# 8. Layer Separation

Business rules must never depend on UI.

UI must never contain business logic.

Database models must not implement workflows.

Controllers must not become business services.

Repositories must not contain UI code.

Services must not know presentation details.

Every layer communicates only through well-defined interfaces.

---

# 9. Dependency Rule

Dependencies always point downward.

Presentation

↓

Application

↓

Domain

↓

Infrastructure

↓

Database

Never reverse dependencies.

Never create circular dependencies.

---

# 10. Architecture First

Implementation is forbidden until architecture exists.

Every implementation must answer:

Which module owns this?

Which workflow uses this?

Which domain contains this?

Which layer implements this?

Which interface exposes this?

If these questions cannot be answered,

implementation is premature.

---

# 11. Domain Ownership

Every feature belongs to exactly one domain.

Example:

Inventory owns products.

Sales owns invoices.

Finance owns expenses.

Identity owns authentication.

Audit owns logs.

No feature should belong to multiple domains.

Communication occurs through services,

never shared ownership.

---

# 12. Single Source of Truth

Every piece of information has exactly one authoritative source.

Examples:

Customer data

→ Customer domain

Product stock

→ Inventory

User permissions

→ Identity

Generated documents

→ Database

Never duplicate authoritative data.

Derived information should always be regenerated.

---

# 13. Business Before Technology

Never select technology because it is fashionable.

Technology exists to support business requirements.

The simplest mature technology that satisfies requirements should be preferred.

---

# 14. Reuse Before Reinvention

Before writing code,

search for mature libraries.

Evaluation criteria:

Maintenance activity

Community adoption

Documentation quality

License compatibility

Long-term support

Reliability

Security

Only implement custom solutions when justified.

---

# 15. Modularity

Every module should be:

Independent

Replaceable

Testable

Documented

Reusable

Well defined

Modules communicate through interfaces.

Never through internal implementation details.

---

# 16. Documentation Standard

Documentation is mandatory.

Every important component documents:

Purpose

Responsibilities

Inputs

Outputs

Dependencies

Limitations

Examples

Future improvements

Documentation evolves together with implementation.

---

# 17. Testing Philosophy

Every important feature should be testable independently.

Testing priorities:

Business Logic

↓

Services

↓

Database

↓

Integration

↓

UI

Business logic should remain testable without the graphical interface.

---

# 18. Performance Philosophy

Correctness first.

Performance second.

Premature optimization is discouraged.

Obvious inefficiencies are unacceptable.

Measure before optimizing.

Optimize using evidence.

---

# 19. Error Philosophy

Errors are expected.

Failures are inevitable.

The system should fail predictably.

Every error should:

Explain what happened.

Explain why.

Provide recovery when possible.

Never expose internal implementation details to end users.

---

# 20. Technical Debt

Technical debt is allowed only when:

Documented.

Justified.

Tracked.

Scheduled for resolution.

Undocumented technical debt is considered a defect.

---

# 21. Simplicity Principle

The best solution is usually the one with:

Fewer abstractions.

Fewer dependencies.

Less code.

Clearer intent.

Greater readability.

Never confuse complexity with sophistication.

---

# 22. Engineering Memory

Engineering decisions persist.

Future decisions must remain compatible unless a documented architectural migration exists.

Never redesign the project from scratch because a new idea appears.

Evolution is preferred over replacement.

---

# 23. Definition of Professional Software

Professional software is software that remains understandable,

maintainable,

predictable,

secure,

and extensible

after years of continuous development.

The objective is not impressive code.

The objective is trustworthy software.

---

# 24. Engineering Oath

Every engineering decision shall be evaluated by asking:

Will this make the software easier to understand?

Will this make future maintenance easier?

Will this reduce future defects?

Will another experienced engineer agree with this decision?

Will this still be the correct decision in five years?

If uncertainty remains,

design again before implementing.

---

# Final Principle

The AI is not rewarded for writing more code.

The AI is rewarded for producing a better engineered system.

Every line of code should exist because it is necessary.

Every component should have a purpose.

Every decision should move the project closer to becoming software that could realistically be maintained and trusted for the next decade.

End of 01_SYSTEM.md