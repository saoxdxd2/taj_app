# 13_DESIGN_SYSTEM.md

Visual Design System (VDS)

Version: 1.0

Status: APPROVED

Authority: Engineering Constitution

Mandatory

---

# Purpose

This document defines the visual identity and interaction principles of TAJ FROID ERP.

The objective is not artistic creativity.

The objective is consistency, clarity, professionalism and efficiency.

Every screen in the ERP must feel like it belongs to the same product.

Users should never feel they are moving between different applications.

---

# Design Philosophy

Professional.

Minimal.

Functional.

Predictable.

Fast.

Comfortable for long working sessions.

The ERP is a business tool.

It is not a marketing website.

It is not a mobile application.

It is not a dashboard made only for screenshots.

---

# Primary Goal

The interface should disappear.

The employee should focus on business operations rather than understanding the software.

---

# Design Principles

• Consistency over originality

• Clarity over decoration

• Readability over density

• Function before animation

• Professionalism before trends

• Every pixel must have a purpose

---

# Visual Identity

The ERP should feel comparable to:

Microsoft Office

Visual Studio

JetBrains IDEs

SAP Business One

Odoo Desktop

Adobe Creative Cloud

Professional accounting software

Never imitate gaming interfaces or flashy dashboards.

---

# Layout System

Use a consistent spacing system.

Base Unit

8 px

Common spacing

8

16

24

32

48

Avoid arbitrary spacing values.

---

# Window Layout

Application

↓

Top Toolbar

↓

Navigation Sidebar

↓

Main Workspace

↓

Status Bar

The layout must remain stable.

Users should develop muscle memory.

---

# Navigation

Navigation must always stay in the same position.

Modules are never moved dynamically.

No hidden navigation.

No hamburger menus on desktop.

---

# Page Structure

Every module follows the same structure.

Header

↓

Toolbar

↓

Filters

↓

Content

↓

Status Summary

Users should instantly recognize any module.

---

# Tables

Tables are the heart of the ERP.

They must be:

Fast

Sortable

Filterable

Resizable

Keyboard friendly

Multi-selection capable

Searchable

Alternating row colors are optional.

Avoid excessive borders.

---

# Forms

Forms must be divided into logical sections.

Never present huge walls of inputs.

Group related fields.

Examples

General

Pricing

Stock

Supplier

Accounting

Notes

Audit

---

# Buttons

Primary action

One per screen

Secondary actions

Limited

Danger actions

Clearly separated

Never place destructive buttons next to confirmation buttons.

---

# Colors

Color communicates meaning.

Never decoration.

Green

Success

Blue

Information

Orange

Warning

Red

Error

Gray

Disabled

Never use color as the only indicator.

---

# Typography

Use system fonts.

Prefer Windows-native rendering.

Hierarchy

Window Title

Section Title

Group Title

Normal Text

Helper Text

Never mix many font sizes.

---

# Icons

Use one icon library only.

Icons support text.

Icons never replace text.

Every important action still has a label.

---

# Search

Every searchable module includes:

Instant search

Advanced filters

Clear filter button

Search state persistence (optional)

---

# Dialogs

Dialogs answer one question only.

Avoid multi-purpose dialogs.

Confirmation dialogs explain consequences.

---

# Notifications

Short.

Actionable.

Professional.

Examples

✓ Invoice created successfully.

✓ Backup completed.

⚠ Stock below minimum.

✗ Cannot delete supplier because invoices exist.

Never display technical exceptions to end users.

---

# Error Messages

Describe

What happened

Why it happened (if known)

How to resolve it

Never expose stack traces.

---

# Empty States

Every empty table explains why it is empty.

Provide the next logical action.

Example

No products found.

Create your first product.

---

# Loading States

Use subtle loading indicators.

Avoid blocking the UI unnecessarily.

Never freeze the interface.

---

# Theme Support

Support:

Light Theme

Dark Theme

System Theme

Themes change appearance only.

Business logic remains unchanged.

---

# High DPI

The application must support:

125%

150%

175%

200%

Windows scaling

No blurry icons.

No clipped text.

---

# Responsive Desktop

The ERP is desktop-first.

Minimum supported resolution

1366 × 768

Recommended

1920 × 1080

Higher resolutions should expose more information rather than simply enlarging controls.

---

# Accessibility

Keyboard navigation.

Logical tab order.

Visible focus indicators.

Readable contrast.

Large click targets.

Consistent shortcuts.

---

# Keyboard Shortcuts

Common shortcuts remain consistent.

Ctrl + N

New

Ctrl + S

Save

Ctrl + F

Search

Ctrl + P

Print

Ctrl + Z

Undo (where appropriate)

Esc

Close dialog

Delete

Delete selected item (with confirmation)

F5

Refresh

---

# Performance Perception

The application should feel instant.

Target

Window opening

<200 ms

Table filtering

Instant

Search

Instant

Dialogs

Immediate

Avoid unnecessary animations.

Responsiveness is more important than visual effects.

---

# Professional Appearance

Avoid:

Rounded elements everywhere

Oversized icons

Bright gradients

Glassmorphism

Neon colors

Excessive shadows

Animated backgrounds

Large hero sections

Fancy startup screens

The ERP should look expensive because it is organized, not because it is flashy.

---

# User Trust

Every important operation should provide confidence.

Examples

Saving...

Saved successfully.

Backup completed.

Invoice printed.

Synchronization completed.

The interface should continuously reassure the user.

---

# Consistency Rules

Every module uses:

The same toolbar layout.

The same search behavior.

The same dialogs.

The same table style.

The same spacing.

The same typography.

The same colors.

The same terminology.

---

# Definition of Premium Software

Premium software is recognized by:

Consistency.

Predictability.

Reliability.

Speed.

Attention to detail.

Not by visual complexity.

The best interface is the one the user stops noticing because it behaves exactly as expected.

---

# Final Principle

The ERP should feel like software built by an experienced engineering team over many years.

It must never feel like a quickly generated application.

Every screen should reinforce confidence, professionalism and long-term reliability.

End of 13_DESIGN_SYSTEM.md