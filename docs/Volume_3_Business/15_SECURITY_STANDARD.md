# 15_SECURITY_STANDARD.md

Enterprise Security Standard (ESS)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

Security protects the confidentiality, integrity and availability of the ERP.

Every engineering decision must consider security from the beginning.

Security is designed into the architecture.

It is never added afterward.

---

# Security Philosophy

The ERP is designed for:

• One company

• One primary computer

• Approximately 11 employees

• Local-first operation

• Future multi-computer support

The architecture must remain secure while avoiding unnecessary complexity.

---

# Security Objectives

Protect business data.

Protect financial information.

Protect customer information.

Protect supplier information.

Protect authentication.

Protect backups.

Protect audit history.

Protect business continuity.

---

# Security Principles

Least Privilege

Every user receives only the permissions required.

---

Defense in Depth

Security is implemented in multiple layers.

UI

↓

Business Logic

↓

Permissions

↓

Database

↓

Audit

---

Secure by Default

Default configuration must always be the safest configuration.

---

Fail Secure

When uncertainty exists:

Reject the operation.

Never silently continue.

---

Never Trust User Input

Every value must be validated.

Even values coming from administrators.

---

# Authentication

Authentication uses:

Username

Password

Passwords are never stored in plaintext.

Use modern password hashing.

Example:

Argon2id (preferred)

or

bcrypt

Administrator accounts are created through the authentication system.

Never hardcode administrator credentials.

---

# Authorization

Authentication answers:

Who are you?

Authorization answers:

What are you allowed to do?

These systems remain independent.

---

# Role-Based Access Control (RBAC)

Version 1

Administrator

Manager

Employee

Future roles may be added without redesign.

Permissions are assigned to roles.

Users inherit permissions.

Never hardcode permissions inside the UI.

---

# Permission Checks

Permission validation occurs inside business services.

Never rely solely on hiding UI buttons.

Hidden buttons are convenience.

Permission enforcement is security.

---

# Sensitive Operations

Require authorization.

Examples

Delete Invoice

Restore Backup

Change Settings

Delete Customer

Delete Supplier

Adjust Stock

Modify Expenses

Restore Database

Manage Users

Manage Roles

---

# Password Policy

Minimum length

Configurable

Passwords never logged.

Passwords never stored in configuration files.

Password reset operations are audited.

---

# Session Management

Every login creates a session.

Logout terminates the session.

Unexpected termination should invalidate the session.

Session timeout should be configurable.

---

# Database Security

Parameterized queries only.

Never concatenate SQL strings.

Transactions protect critical operations.

Database constraints enforce integrity.

---

# Input Validation

Validate:

Type

Length

Format

Business Rules

Database Constraints

Never trust UI validation alone.

---

# Secrets

Secrets include:

Passwords

API Keys

Tokens

Encryption Keys

Never store secrets inside source code.

Never commit secrets to Git.

Use environment variables or secure configuration storage.

---

# Logging

Sensitive information must never appear in logs.

Forbidden

Passwords

Authentication tokens

Private keys

Sensitive customer notes

---

# Audit

Every security-sensitive operation generates an immutable audit event.

Examples

Login

Logout

Failed Login

Role Change

Password Change

Permission Change

Backup Restore

Configuration Change

---

# File Security

Validate imported files.

Reject unsupported formats.

Validate file size.

Never execute imported files.

Never trust filenames.

---

# Backup Security

Backups must be verifiable.

Corrupted backups must be detected.

Backup creation is audited.

Backup restoration is audited.

Automatic backups must never overwrite the only valid backup.

---

# Error Handling

Users receive understandable messages.

Developers receive technical details through logs.

Never expose:

SQL queries

Stack traces

Internal paths

Secrets

---

# OCR Security

OCR imports are treated as untrusted input.

Extracted values require validation before database insertion.

Automation never bypasses business rules.

---

# Printing

Printing never bypasses permissions.

Generated PDFs inherit document permissions.

---

# Future Networking

Current version:

Local-only.

Future networking must support:

TLS

Secure authentication

Encrypted communication

Without redesigning business logic.

---

# Security Reviews

Every new feature must answer:

What data does it access?

Who may access it?

Can permissions be bypassed?

Does it affect financial records?

Does it affect audit history?

Does it expose sensitive information?

---

# Security Checklist

Before release verify:

✓ Password hashing

✓ Permission checks

✓ Input validation

✓ Secure transactions

✓ Audit coverage

✓ Secrets protected

✓ Logs sanitized

✓ Backup verified

✓ Session handling correct

✓ No hardcoded credentials

---

# Final Principle

A feature is not complete simply because it works.

It is complete only when it works securely.

End of 15_SECURITY_STANDARD.md