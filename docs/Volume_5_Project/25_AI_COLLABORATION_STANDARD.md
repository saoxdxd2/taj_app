# 25_AI_COLLABORATION_STANDARD.md

AI Collaboration Standard (AICS)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

This standard defines how AI engineering agents collaborate on the project across different sessions, models and time.

The objective is to ensure that every engineering session contributes consistently to the same project regardless of which AI model performs the work.

The project must depend on documented engineering knowledge rather than conversational memory.

---

# Philosophy

No AI session owns the project.

Every AI session is a temporary engineering contributor.

The repository is the permanent source of truth.

Knowledge belongs to the project.

Not to the current conversation.

---

# Source of Truth Hierarchy

When information conflicts, consult the following hierarchy:

1. Engineering Constitution
2. Engineering Decision Records (EDRs)
3. PROJECT_MEMORY.md
4. Approved Documentation
5. TASK_MEMORY.md
6. Current Conversation

Higher-priority sources always prevail unless formally superseded.

---

# Session Independence

Every engineering session must be able to begin with:

START_HERE.md

MASTER_INDEX.md

PROJECT_MEMORY.md

TASK_MEMORY.md

Required engineering documents for the current task.

No previous conversation should be required.

---

# Engineering Handoff

At the end of every completed session:

Update TASK_MEMORY.md.

Update PROJECT_MEMORY.md if durable knowledge changed.

Update documentation.

Record unresolved issues.

Recommend exactly one next engineering task.

The next session should resume without rediscovering previous work.

---

# Conflict Resolution

When documentation conflicts:

Do not guess.

Identify the conflict.

Reference the affected documents.

Recommend the appropriate Engineering Decision Record.

Never silently choose one interpretation.

---

# Temporary Reasoning

Exploration belongs to the current session only.

Temporary reasoning should not be preserved unless it results in a durable engineering decision.

Discard exploratory thoughts after completion.

---

# Project Consistency

Before implementation verify:

Architecture consistency.

Business rule consistency.

Database consistency.

Naming consistency.

Documentation consistency.

Consistency is more important than implementation speed.

---

# AI Responsibilities

Every engineering agent is responsible for:

Improving the project.

Preserving architectural quality.

Avoiding unnecessary complexity.

Respecting previous accepted decisions.

Leaving the repository in a better state.

---

# Cross-Model Compatibility

Engineering documents must remain understandable by:

Future GPT models.

Future Gemini models.

Future Claude models.

Future open-source models.

Avoid model-specific instructions whenever practical.

---

# Communication Between Sessions

AI sessions communicate only through:

Documentation.

Engineering Decision Records.

Project Memory.

Task Memory.

Release Notes.

Conversations are temporary and should not become project dependencies.

---

# Engineering Humility

Assume previous engineers acted with good intentions.

Question decisions using evidence rather than assumptions.

When proposing changes:

Explain why.

Document consequences.

Preserve history.

---

# Continuous Improvement

An engineering agent is encouraged to improve:

Documentation.

Architecture.

Maintainability.

Performance.

Developer experience.

However, improvements must remain within the current task's approved scope unless a new task is created.

---

# Forbidden Behaviors

Do not:

Ignore established standards.

Rewrite architecture without justification.

Duplicate functionality.

Replace mature components without evidence.

Accumulate undocumented technical debt.

Treat conversations as permanent project memory.

---

# Success Criteria

A successful collaboration means:

A different AI model can continue the project tomorrow with minimal onboarding.

The project remains coherent despite changes in contributors.

No engineering knowledge is lost between sessions.

---

# Engineering Principle

The project should improve regardless of which engineer—human or AI—works on it.

Consistency, documentation and shared understanding are the foundations of successful collaboration.

End of 25_AI_COLLABORATION_STANDARD.md