# 20_DIRECTORY_STRUCTURE.md

Repository Structure Standard (RSS)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

This document defines the official directory structure of the TAJ FROID ERP repository.

A predictable structure improves:

• Navigation

• Maintainability

• Onboarding

• AI consistency

• Reusability

Every file has a logical home.

No directory should become a miscellaneous storage location.

---

# Top-Level Structure

project/

│

├── engineering/

├── docs/

├── src/

├── tests/

├── resources/

├── migrations/

├── backups/

├── scripts/

├── tools/

├── config/

├── data/

├── logs/

├── build/

├── dist/

└── README.md

---

# engineering/

Contains engineering process documentation.

Examples

START_HERE.md

MASTER_INDEX.md

PROJECT_MEMORY.md

TASK_MEMORY.md

tasks/

reviews/

retrospectives/

edr/

templates/

This folder explains HOW the project is developed.

---

# docs/

Contains permanent project documentation.

Volumes

Volume 0 — Constitution

Volume 1 — Engineering

Volume 2 — Architecture

Volume 3 — Business

Volume 4 — Development

Volume 5 — Project

This folder explains WHAT the project is.

---

# src/

Application source code.

Suggested structure

src/

core/

services/

models/

repositories/

controllers/

modules/

ui/

widgets/

dialogs/

resources/

localization/

printing/

ocr/

backup/

security/

audit/

logging/

database/

utils/

The source code should reflect the architecture.

---

# modules/

Each business module owns its logic.

Example

inventory/

sales/

crm/

suppliers/

finance/

dashboard/

reports/

settings/

authentication/

Each module should remain as independent as practical.

---

# tests/

tests/

unit/

integration/

database/

ui/

performance/

fixtures/

Every test belongs to exactly one category.

---

# resources/

Static resources.

icons/

themes/

translations/

fonts/

templates/

images/

No business logic belongs here.

---

# migrations/

Database migrations.

Ordered.

Versioned.

Never manually edited after release.

---

# backups/

Automatic backups.

Manual backups.

Verification reports.

Temporary restoration data.

---

# scripts/

Development utilities.

Database initialization.

Maintenance.

Build helpers.

Migration helpers.

Never import application business logic into scripts unnecessarily.

---

# tools/

Internal engineering tools.

Code generation.

Diagnostics.

Validation.

Migration helpers.

Analysis tools.

These support development rather than the ERP itself.

---

# config/

Configuration files.

Default settings.

Environment configuration.

Application configuration.

No secrets stored here.

---

# data/

Development datasets.

Sample OCR files.

Demo templates.

Import examples.

Never production customer data.

---

# logs/

Application logs.

Rotated automatically.

Ignored by Git.

---

# build/

Temporary build artifacts.

Generated automatically.

Safe to delete.

---

# dist/

Production packages.

Installers.

Executable builds.

Release artifacts.

Generated automatically.

---

# Naming Rules

Directories

lowercase

snake_case

Python packages

snake_case

Python files

snake_case

Classes

PascalCase

Functions

snake_case

Constants

UPPER_CASE

---

# Module Independence

Business modules should communicate through services and defined interfaces.

Avoid direct module-to-module dependencies whenever practical.

---

# Forbidden Practices

Do not create folders such as

misc/

temp/

new/

test2/

backup_old/

final_final/

etc/

Directory names must communicate purpose.

---

# Git Rules

Generated files

Ignored

Logs

Ignored

Builds

Ignored

Virtual environments

Ignored

Temporary files

Ignored

Source code

Tracked

Documentation

Tracked

Engineering documents

Tracked

---

# Future Expansion

The structure must support:

Multi-company

Plugins

REST API

Cloud synchronization

Mobile companion app

Barcode module

Warehouse module

Without major reorganization.

---

# Engineering Principle

A developer should be able to locate any file within seconds based solely on the repository structure.

If a file has no obvious location, the structure should be improved rather than creating an ambiguous folder.

End of 20_DIRECTORY_STRUCTURE.md