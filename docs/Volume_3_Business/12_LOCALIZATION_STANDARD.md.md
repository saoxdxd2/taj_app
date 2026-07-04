# 12_LOCALIZATION_STANDARD.md

Localization Engineering Standard (LES)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

This document defines every rule related to localization and internationalization within TAJ FROID ERP.

Localization is part of the software architecture.

It is never treated as an afterthought.

No visible user interface text may be hardcoded.

---

# Objectives

The ERP must support multiple languages without requiring source code modification.

The initial supported languages are:

• French

• English

The architecture must allow future languages to be added without redesign.

---

# Definitions

Internationalization (i18n)

Designing the application so it can support multiple languages.

Localization (l10n)

Providing translated resources for a specific language.

Translation

The textual content itself.

The project performs localization.

It does not perform automatic translation.

---

# Supported Languages

Version 1

✓ French

✓ English

Future

Arabic

Spanish

German

Others

---

# Translation Source

Translations are maintained manually.

Machine translation is forbidden.

Every translation must be reviewed by a human.

---

# User Interface Rule

Never write visible text directly inside Python source code.

Forbidden

QPushButton("Add Product")

Required

QPushButton(_("inventory.add_product"))

---

# Translation Keys

Keys are stable.

Keys never depend on displayed text.

Example

inventory.add_product

inventory.delete_product

sales.create_invoice

settings.language

authentication.login

---

# Naming Convention

module.section.element

Examples

inventory.table.stock

inventory.table.price

crm.customer.phone

crm.customer.city

sales.invoice.total

settings.general.language

---

# Translation Files

resources/

translations/

fr/

inventory.json

sales.json

crm.json

settings.json

system.json

en/

inventory.json

sales.json

crm.json

settings.json

system.json

Each module owns its translations.

---

# Dynamic Language Switching

The application shall support changing language from Settings.

Preferred behavior:

Language change

↓

Save preference

↓

Restart application

↓

Reload all translated resources

Runtime switching is optional.

Correctness is preferred over complexity.

---

# Documents

Application language

and

Document language

are independent.

Example

ERP Interface

English

↓

Invoice

French

This allows multilingual employees while producing customer documents in the required language.

---

# Dates

Store internally in ISO format.

Display according to selected locale.

---

# Numbers

Internal representation is locale independent.

Display follows selected locale.

---

# Currency

Business currency:

Moroccan Dirham (DH)

Currency formatting must remain configurable for future expansion.

---

# Images

Do not embed language into images.

Use icons whenever possible.

If text exists inside an image, localized versions must be provided.

---

# Error Messages

All validation messages

Warnings

Errors

Tooltips

Dialogs

Notifications

must use localization keys.

---

# OCR

OCR templates remain independent of UI language.

OCR extraction logic must never depend on translated interface text.

---

# Reports

Generated reports must support language selection independently from the application interface.

---

# Accessibility

Localization must preserve:

Readable layouts

Keyboard shortcuts where possible

Consistent terminology

Professional wording

---

# Terminology

Business vocabulary must remain consistent.

Example

Invoice

always maps to the same translation.

Never alternate between synonyms.

---

# Quality Checklist

Before release verify:

✓ No hardcoded UI strings

✓ Translation keys exist

✓ Missing keys detected

✓ Consistent terminology

✓ Reports localized

✓ Dialogs localized

✓ Error messages localized

✓ Tooltips localized

✓ Settings localized

✓ Future language compatibility preserved

---

# Forbidden Practices

Do not:

Hardcode visible strings.

Generate translations using AI during runtime.

Mix multiple languages on one screen.

Duplicate translation keys.

Use displayed text as identifiers.

---

# Final Principle

The language of the interface must never influence business logic.

Business logic remains language-neutral.

Localization changes presentation only.

End of 12_LOCALIZATION_STANDARD.md