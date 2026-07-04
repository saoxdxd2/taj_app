# 22_RELEASE_AND_VERSIONING_STANDARD.md

Enterprise Release & Versioning Standard (ERVS)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

This standard defines how the TAJ FROID ERP is versioned, released, packaged and maintained throughout its lifecycle.

Every release must be predictable, reproducible and traceable.

A release is a business event, not merely a compiled executable.

---

# Versioning Philosophy

The ERP follows Semantic Versioning.

Format:

MAJOR.MINOR.PATCH

Example:

1.0.0

---

# Version Definitions

MAJOR

Breaking architectural or business changes.

Examples:

Database redesign

Permission redesign

Major workflow redesign

---

MINOR

Backward-compatible feature additions.

Examples:

New module

New report

New OCR template

New dashboard widget

New language

---

PATCH

Bug fixes.

Performance improvements.

Security fixes.

Documentation corrections.

No business behavior changes.

---

# Release Types

Development

Internal engineering only.

---

Alpha

Incomplete.

Not for production.

Major changes expected.

---

Beta

Feature complete.

Business validation phase.

Limited production testing.

---

Release Candidate (RC)

Expected to become production.

Only critical fixes permitted.

---

Stable

Approved for daily business use.

---

Hotfix

Emergency correction to a Stable release.

Only critical production issues.

---

# Release Naming

Every release contains:

Version

Release date

Engineering summary

Migration status

Known limitations

Reference to release notes

Example:

TAJ FROID ERP v1.2.0

---

# Release Notes

Every release generates release notes containing:

Overview

New Features

Improvements

Bug Fixes

Database Changes

Security Changes

Known Issues

Migration Instructions

Breaking Changes

Future Work

---

# Database Versioning

Application version

and

Database schema version

are tracked independently.

Example:

Application

1.2.0

Database

Schema 9

This prevents migration ambiguity.

---

# Migration Rules

Every schema change requires:

Migration script

Rollback strategy (when practical)

Validation

Documentation update

Migration testing

---

# Packaging

Official production builds include only:

Executable

Required runtime

Resources

Localization files

Templates

Configuration

License

Documentation

Development files are excluded.

---

# Build Identification

Every production build records:

Application version

Git commit (if available)

Build timestamp

Database schema version

Python version

PySide6 version

Operating System

This information assists support and debugging.

---

# Upgrade Rules

Upgrades must preserve:

Business data

Audit history

Journal history

User accounts

Permissions

Configuration

Localization

User preferences

No upgrade may silently destroy data.

---

# Rollback

When practical:

Previous stable version should remain recoverable.

Backups must be created automatically before database migrations.

---

# Compatibility

Patch releases

Fully compatible.

Minor releases

Backward compatible whenever practical.

Major releases

May introduce controlled breaking changes.

These must be documented.

---

# Release Approval

A Stable release requires:

Definition of Done satisfied

No Critical bugs

No High severity bugs

Documentation complete

Database validated

Backup verified

Migration tested

Engineering review completed

---

# Emergency Releases

Emergency releases bypass normal scheduling.

They do not bypass engineering quality.

Even urgent fixes require:

Testing

Documentation

Version increment

Release notes

---

# Long-Term Support (LTS)

Future major versions may designate LTS releases.

LTS receives:

Security fixes

Critical bug fixes

Database compatibility

Without introducing new features.

---

# Distribution

Official releases are distributed only through approved company channels.

Internal development builds must never replace Stable production installations.

---

# Engineering Principle

Every release should increase confidence in the software.

A version number represents a commitment to quality, stability and traceability—not simply a snapshot of the code.

End of 22_RELEASE_AND_VERSIONING_STANDARD.md