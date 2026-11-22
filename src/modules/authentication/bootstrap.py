"""Idempotent security bootstrap for fresh and existing databases.

The original startup code only inserted a permission or role when the row
was missing. That is enough for a brand-new database, but it means an
existing installation never receives permissions added by a later
release. The UI would then hide the new feature and the service would
reject the call even for an administrator whose role predates it.

This module owns the complete built-in permission catalog and reconciles
it on every start:

* missing permissions are inserted;
* the Administrator role always receives the ``.*`` superuser grant;
* the built-in Manager and Employee roles receive any permission that was
  added to their definition after the role was created;
* existing grants are never removed, so a local customization survives.

The bootstrap administrator is still created only when no Administrator
user exists at all. The desktop entry point then starts a local session as
that account; there is no interactive login screen.
"""
from __future__ import annotations

from typing import Dict, List

from loguru import logger

from src.modules.authentication.models import Permission, Role, User
from src.modules.authentication.services import AuthenticationService


# Every permission checked by a service or by the UI. Keeping this list in
# one place means a new ``verify_permission("...")`` call cannot be
# forgotten during startup seeding.
PERMISSION_DESCRIPTIONS: Dict[str, str] = {
    ".*": "Superuser access to every feature",
    "Inventory.*": "Full inventory access",
    "CRM.*": "Full customer access",
    "Suppliers.*": "Full supplier access",
    "Sales.*": "Full sales access",
    "Purchasing.*": "Full purchasing access",
    "Inventory.Brands.View": "View brands",
    "Inventory.Categories.View": "View categories",
    "Inventory.Products.View": "View products",
    "Inventory.Products.Create": "Create products",
    "Inventory.Products.Update": "Edit products and stock",
    "Inventory.Products.Archive": "Archive products",
    "Inventory.Stock.View": "View stock levels and movements",
    "Inventory.Stock.Update": "Adjust stock levels",
    "Inventory.Attributes.View": "View product attributes",
    "Inventory.Attributes.Create": "Create product attributes",
    "Inventory.Attributes.Update": "Edit product attributes",
    "Inventory.Attributes.Delete": "Delete product attributes",
    "CRM.Customers.View": "View customers",
    "CRM.Customers.Create": "Create customers",
    "CRM.Customers.Update": "Edit customers",
    "CRM.Customers.Archive": "Archive customers",
    "Suppliers.Suppliers.View": "View suppliers",
    "Suppliers.Suppliers.Create": "Create suppliers",
    "Suppliers.Suppliers.Update": "Edit suppliers",
    "Suppliers.Suppliers.Archive": "Archive suppliers",
    "Purchasing.Purchases.View": "View purchase orders",
    "Purchasing.Purchases.Create": "Create purchase orders",
    "Purchasing.Purchases.Update": "Edit purchase orders",
    "Purchasing.Purchases.Validate": "Validate and receive purchase orders",
    "Sales.Invoices.View": "View sales invoices",
    "Sales.Invoices.Create": "Create sales invoices",
    "Sales.Invoices.Update": "Edit draft sales invoices",
    "Sales.Invoices.Validate": "Validate sales invoices",
    "Sales.Payments.Create": "Record customer payments",
    "Sales.Deposits.Create": "Record customer deposits",
    "Sales.Deposits.Use": "Apply deposits to invoices",
    "Sales.Returns.Create": "Create sales returns",
    "Sales.Returns.Validate": "Validate sales returns",
    "Finance.Checks.View": "View the check ledger",
    "Finance.Checks.Create": "Register checks",
    "Finance.Checks.Update": "Clear, bounce or cancel checks",
    "Finance.Reports.View": "View cash-flow and debtor reports",
    "Accounting.Accounts.View": "View cash/bank accounts and their ledger",
    "Accounting.Accounts.Manage": "Create accounts, deposit, withdraw and transfer funds",
    "Accounting.Methods.View": "View the payment-method catalog",
    "Accounting.Methods.Manage": "Create, edit and deactivate payment methods",
    "Accounting.Reconciliation.View": "View imported bank statements and their lines",
    "Accounting.Reconciliation.Manage": "Import statements, categorize and match bank lines",
    "Pricing.Policies.View": "View pricing policies",
    "Pricing.Policies.Create": "Create pricing policies",
    "Pricing.Policies.Delete": "Delete pricing policies",
    "Reports.Profit.View": "View profit reports",
    "Settings.Company.View": "View company identity settings",
    "Settings.Company.Update": "Edit company identity settings",
    "Settings.System.Update": "Manage backups, diagnostics and database maintenance",
    "Settings.WebsiteSync.Export": "Export the website catalog and change its folder",
    "Settings.WebsiteSync.Import": "Import website price updates",
    AuthenticationService.PERM_USERS_VIEW: "View user accounts",
    AuthenticationService.PERM_USERS_CREATE: "Create user accounts",
    AuthenticationService.PERM_USERS_UPDATE: "Enable, disable and reset user accounts",
}

MANAGER_PERMISSIONS: List[str] = [
    "Inventory.*",
    "CRM.*",
    "Suppliers.*",
    "Sales.*",
    "Purchasing.*",
]

EMPLOYEE_PERMISSIONS: List[str] = [
    "Inventory.Products.View",
    "CRM.Customers.View",
    "Sales.Invoices.Create",
]

def _ensure_permission(session, name: str) -> Permission:
    permission = session.query(Permission).filter(Permission.name == name).first()
    if permission is None:
        permission = Permission(
            name=name,
            description=PERMISSION_DESCRIPTIONS.get(name, name),
        )
        session.add(permission)
        session.flush()
    return permission


def _ensure_role(session, name: str, description: str,
                 permission_names: List[str]) -> Role:
    role = session.query(Role).filter(Role.name == name).first()
    if role is None:
        role = Role(name=name, description=description)
        session.add(role)
        session.flush()

    granted = {permission.name for permission in role.permissions}
    for permission_name in permission_names:
        if permission_name in granted:
            continue
        role.permissions.append(_ensure_permission(session, permission_name))
        granted.add(permission_name)
    return role


def seed_security_data(session) -> Dict[str, int]:
    """Creates missing permissions/roles and reconciles built-in grants.

    Returns a small report suitable for logging. The caller owns the
    transaction and must commit (or roll back) it.
    """
    before_permissions = session.query(Permission).count()
    before_roles = session.query(Role).count()

    for name in PERMISSION_DESCRIPTIONS:
        _ensure_permission(session, name)
    session.flush()

    admin_role = _ensure_role(
        session, AuthenticationService.ADMIN_ROLE, "System Administrator", [".*"]
    )
    _ensure_role(session, "Manager", "Department Manager", MANAGER_PERMISSIONS)
    _ensure_role(session, "Employee", "Standard Employee", EMPLOYEE_PERMISSIONS)
    session.flush()

    report = {
        "permissions_added": session.query(Permission).count() - before_permissions,
        "roles_added": session.query(Role).count() - before_roles,
    }
    if report["permissions_added"] or report["roles_added"]:
        logger.info(
            "Security bootstrap reconciled %s permission(s) and %s role(s).",
            report["permissions_added"],
            report["roles_added"],
        )
    return report


def ensure_bootstrap_admin(session) -> bool:
    """Creates the factory administrator only when none exists.

    Returns True when a new account was created. The factory password is
    left in place because the desktop build signs in locally without
    asking for it.
    """
    admin_role = (
        session.query(Role)
        .filter(Role.name == AuthenticationService.ADMIN_ROLE)
        .first()
    )
    if admin_role is None:
        raise RuntimeError(
            "Administrator role is missing; seed_security_data must run first."
        )

    existing = session.query(User).filter(User.role_id == admin_role.id).first()
    if existing is not None:
        return False

    admin = User(
        username="admin",
        password_hash=AuthenticationService.hash_password(
            AuthenticationService.DEFAULT_ADMIN_PASSWORD
        ),
        role_id=admin_role.id,
    )
    session.add(admin)
    session.flush()
    logger.warning(
        "Created the bootstrap administrator with the factory password. "
        "The desktop app signs in locally as this account."
    )
    return True


def initialize_security(session) -> Dict[str, object]:
    """Convenience entry point used by application startup."""
    report = seed_security_data(session)
    report["bootstrap_admin_created"] = ensure_bootstrap_admin(session)
    return report
