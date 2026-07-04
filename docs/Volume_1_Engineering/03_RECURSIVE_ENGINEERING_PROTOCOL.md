# 03_RECURSIVE_ENGINEERING_PROTOCOL.md

# Recursive Engineering Protocol (REP)

Version: 1.0

Status: IMMUTABLE

---

# Purpose

This document defines the mandatory engineering process used to solve every problem within this project.

The objective of REP is not to produce an answer quickly.

The objective is to converge toward the highest-quality engineering solution that is reasonable within the project's constraints.

REP is mandatory for every feature, bug fix, refactor, architectural decision, performance improvement, documentation update and design task.

---

# Fundamental Principle

The first solution is only a candidate.

It is never automatically accepted as the final solution.

Every solution must survive multiple engineering reviews before it is considered complete.

---

# Engineering Mindset

You are not attempting to satisfy the user's request as quickly as possible.

You are attempting to build software that another senior engineer would be willing to maintain for many years.

Every answer should reflect professional engineering judgment.

---

# Engineering Objectives

Every engineering cycle should improve one or more of the following:

- Business correctness
- Simplicity
- Reliability
- Security
- Maintainability
- Testability
- Readability
- Performance
- Documentation
- Reusability

If no measurable improvement is achieved, reconsider whether the work is necessary.

---

# The Recursive Cycle

Every task follows this sequence.

1. Understand

↓

2. Clarify

↓

3. Research

↓

4. Analyze

↓

5. Design

↓

6. Critique

↓

7. Improve

↓

8. Validate

↓

9. Implement

↓

10. Review

↓

11. Refactor

↓

12. Test

↓

13. Document

↓

14. Evaluate

↓

Repeat if a material improvement is still possible.

---

# Stage 1 — Understand

Before proposing any solution:

Determine the real business problem.

Separate symptoms from root causes.

Determine:

Who is affected?

Why does the problem exist?

What business process is involved?

What constraints exist?

What assumptions are being made?

Never solve a misunderstood problem.

---

# Stage 2 — Clarify

Identify missing information.

List unknowns.

Avoid hidden assumptions.

If assumptions are unavoidable:

State them explicitly.

Estimate their confidence.

Proceed cautiously.

---

# Stage 3 — Research

Before implementing anything:

Determine whether an existing solution already exists.

Evaluate:

Python standard library

Well-maintained libraries

Existing project code

Framework capabilities

Operating system capabilities

Never recreate mature functionality without justification.

---

# Stage 4 — Analyze

Identify:

Dependencies

Risks

Failure modes

Edge cases

Security concerns

Performance concerns

Maintainability concerns

Long-term consequences

Do not continue until the problem space is fully understood.

---

# Stage 5 — Design

Produce the design before implementation.

Define:

Responsibilities

Interfaces

Data flow

Ownership

Dependencies

Validation strategy

Error strategy

Testing strategy

If architecture changes,

update architecture before code.

---

# Stage 6 — Critique

Assume the current design is imperfect.

Ask:

Can it be simpler?

Can duplication be removed?

Can responsibilities be reduced?

Can existing components be reused?

Can dependencies decrease?

Can complexity decrease?

Would another experienced engineer understand this immediately?

---

# Stage 7 — Improve

Apply improvements discovered during critique.

Repeat critique if major changes occur.

Optimization should be guided by evidence, not preference.

---

# Stage 8 — Validate

Verify:

Business correctness

Architecture consistency

Layer separation

Security

Database integrity

User workflow

Data ownership

Permissions

Audit implications

Performance expectations

Validation occurs before implementation.

---

# Stage 9 — Implement

Only now is implementation allowed.

Implementation must follow:

Project DNA

Architecture

Coding standards

Module contracts

Database philosophy

Audit standard

Implementation should never redesign architecture.

---

# Stage 10 — Review

Immediately review the implementation.

Check:

Readability

Consistency

Naming

Dependencies

Documentation

Logging

Transactions

Permissions

Complexity

Avoid becoming attached to the first implementation.

---

# Stage 11 — Refactor

Refactoring is mandatory.

Reduce:

Duplication

Coupling

Complexity

Large functions

Large classes

Poor naming

Magic values

Technical debt

Refactoring must preserve behavior.

---

# Stage 12 — Test

Verify:

Business rules

Normal inputs

Boundary conditions

Invalid inputs

Permission failures

Database consistency

Integration

Regression

Never assume correctness because the code compiles.

---

# Stage 13 — Document

Update:

Architecture

Module documentation

Project memory

Changelog

Engineering decisions

Future improvements

Documentation is part of the implementation.

---

# Stage 14 — Evaluate

Determine:

Can this solution realistically be improved?

Would another engineering cycle produce meaningful value?

If yes:

Repeat the cycle.

If no:

Stop.

---

# Engineering Confidence

Every significant recommendation should internally include a confidence assessment.

Confidence Levels:

High

Backed by:

Industry standards

Extensive experience

Strong evidence

Stable technologies

---

Medium

Backed by:

Reasonable engineering judgment

Partial evidence

Acceptable trade-offs

---

Low

Backed by:

Assumptions

Limited information

Experimental approaches

Unknown future constraints

Never present Low confidence decisions as certain.

---

# Decision Analysis

For every important technical decision evaluate:

Decision

↓

Evidence

↓

Alternatives

↓

Advantages

↓

Disadvantages

↓

Risk

↓

Confidence

↓

Recommendation

---

# Architectural Drift Prevention

Before changing architecture:

Determine whether the decision conflicts with existing architecture.

If conflict exists:

Review previous architectural decisions.

Determine whether migration is justified.

Do not redesign architecture casually.

Evolution is preferred over replacement.

---

# Self-Critique

Before declaring any task complete, ask:

Is this the simplest reasonable solution?

Is this maintainable?

Is this secure?

Is this testable?

Is this reusable?

Is this documented?

Is business logic separated?

Would I approve this in a professional code review?

If any answer is uncertain:

Continue improving.

---

# Stop Conditions

The recursive process may stop only when:

All acceptance criteria are satisfied.

Architecture remains consistent.

No critical defects remain.

Tests pass.

Documentation is updated.

No significant engineering improvement is reasonably expected.

Perfection is not required.

Professional quality is.

---

# Forbidden Behaviors

Do not:

- Jump directly into implementation.
- Redesign architecture while coding.
- Introduce unnecessary abstractions.
- Duplicate business logic.
- Ignore documentation.
- Ignore testing.
- Ignore security implications.
- Ignore long-term maintenance.
- Reinvent mature libraries without justification.
- Hide uncertainty.

---

# Engineering Discipline

Speed is valuable.

Correctness is more valuable.

Elegance is valuable.

Maintainability is more valuable.

Innovation is valuable.

Reliability is more valuable.

Always optimize for the lifetime of the software, not the speed of producing the first version.

---

# Final Principle

Engineering is the process of reducing uncertainty.

Implementation is only one consequence of good engineering.

Never measure success by the amount of code written.

Measure success by the quality, longevity and trustworthiness of the resulting system.

End of 03_RECURSIVE_ENGINEERING_PROTOCOL.md