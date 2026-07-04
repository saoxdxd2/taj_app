# TAJ FROID ERP
# Engineering Constitution

Version: 1.0

Status: SUPREME LAW

Priority: Highest

---

# Purpose

This constitution defines the engineering philosophy of the TAJ FROID ERP.

It is the highest authority of the project.

Every source file, every module, every document, every design decision, every database migration and every future contribution must comply with this constitution.

If any implementation contradicts this constitution, the implementation is wrong.

---

# Vision

Build a professional desktop ERP that can reliably operate a real company for many years.

The objective is not to create software that merely works.

The objective is to create software that employees trust every day.

The ERP must feel like a premium commercial product developed by an experienced engineering team.

---

# Mission

Replace fragmented manual workflows, Excel spreadsheets and repetitive accounting tasks with a reliable, maintainable and auditable business platform.

The ERP becomes the operational memory of TAJ FROID.

---

# Engineering Philosophy

Engineering quality is more important than implementation speed.

Correctness is more important than cleverness.

Maintainability is more important than short-term optimization.

Reliability is more important than feature count.

Professionalism is more important than visual effects.

Every decision should improve the project for the next ten years.

---

# Core Principles

## 1. Business First

The software exists to support business processes.

Business requirements drive architecture.

The software never forces the company to adopt unnecessary workflows.

---

## 2. Production From Day One

This project never produces "temporary" production code.

Every accepted implementation is expected to remain in production.

Prototype code, demo code and throwaway implementations are forbidden.

---

## 3. Build Forward

Every commit moves the ERP closer to its final architecture.

Features are refined incrementally.

They are not rewritten because of poor initial planning.

---

## 4. Architecture Before Code

Before implementation:

Understand the problem.

Study dependencies.

Research mature libraries.

Design the architecture.

Review trade-offs.

Only then write code.

---

## 5. Reuse Before Reinvention

Before implementing functionality:

- Search Python's standard library.
- Search mature open-source libraries.
- Search existing project modules.

If a proven solution exists, prefer integration over reinvention.

---

## 6. Separation of Responsibilities

Business logic.

Database.

User interface.

Services.

Repositories.

Infrastructure.

Testing.

Documentation.

Remain independent.

Each component has a single responsibility.

---

## 7. Long-Term Thinking

Every engineering decision should assume the software will still be used ten years from today.

Avoid shortcuts that create future technical debt.

---

## 8. Simplicity Wins

Prefer simple, understandable solutions over clever complexity.

If two implementations provide equivalent value, choose the simpler one.

---

## 9. Measure Before Optimizing

Do not optimize because something "might" be slow.

Measure.

Identify bottlenecks.

Optimize only where evidence justifies it.

---

## 10. Documentation Is Part of the Product

Documentation is not optional.

Code changes require documentation updates when behavior or architecture changes.

The documentation must always describe the current system.

---

# Production Rules

No prototype contamination.

No placeholder implementations presented as production.

No "temporary" hacks.

No hidden technical debt.

No undocumented architectural changes.

No silent breaking changes.

No duplicated business logic.

No hardcoded administrator accounts.

No hardcoded secrets.

No direct database manipulation outside approved layers.

---

# Engineering Decision Process

For every significant implementation:

1. Understand the business objective.
2. Identify constraints.
3. Research existing solutions.
4. Evaluate alternatives.
5. Select the simplest robust architecture.
6. Validate against this constitution.
7. Implement.
8. Test.
9. Review.
10. Document.
11. Merge.

---

# Quality Commitment

Every completed feature must be:

Correct.

Tested.

Documented.

Auditable.

Maintainable.

Secure.

Readable.

Recoverable.

Future-proof.

---

# Definition of Professional Software

Professional software is software that:

Users trust.

Engineers understand.

Managers can rely on.

Future developers can extend safely.

The business can operate without fear of data loss or hidden behavior.

---

# AI Development Policy

Artificial intelligence is an engineering assistant.

It is not an architect.

It is not a product owner.

It is not the business.

Every AI-generated solution must satisfy the same engineering standards expected from experienced human engineers.

Convenience is never accepted as justification for poor architecture.

---

# Continuous Improvement

The architecture may evolve.

The implementation may improve.

Libraries may change.

Technology may advance.

However, improvements must preserve the principles established by this constitution.

Evolution is encouraged.

Architectural drift is forbidden.

---

# Final Oath

Every contribution to this repository should leave the project in a better state than it was found.

If an implementation increases complexity without increasing long-term value, it should not be accepted.

The objective is not merely to finish the ERP.

The objective is to build an ERP that remains understandable, reliable and trusted for many years.

This constitution defines that commitment.

## Respect the Intelligence of the Engineer

This Engineering Manual defines objectives, constraints, architectural principles and quality standards.

It intentionally avoids prescribing implementation details when multiple valid solutions exist.

Human engineers and AI engineering agents are expected to apply professional judgment within these constraints.

Innovation is encouraged.

Architectural inconsistency is not.

End of 00_ENGINEERING_CONSTITUTION.md