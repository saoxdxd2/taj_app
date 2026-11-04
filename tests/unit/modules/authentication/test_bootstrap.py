"""Security bootstrap must reconcile existing databases, not just new ones.

Regression: startup used to insert a permission only when it was absent,
so a database created by an older release never received permissions
added later. The UI then hid the feature and the service rejected even an
administrator because their role predated the permission.
"""
from src.modules.authentication.bootstrap import (
    EMPLOYEE_PERMISSIONS,
    MANAGER_PERMISSIONS,
    PERMISSION_DESCRIPTIONS,
    ensure_bootstrap_admin,
    initialize_security,
    seed_security_data,
)
from src.modules.authentication.models import Permission, Role, User
from src.modules.authentication.services import AuthenticationService


def _permission_names(session):
    return {p.name for p in session.query(Permission).all()}


def test_seed_creates_the_complete_permission_catalog(session):
    seed_security_data(session)
    session.commit()

    names = _permission_names(session)
    assert ".*" in names
    assert "Finance.Checks.View" in names
    assert "Settings.System.Update" in names
    assert "Settings.WebsiteSync.Export" in names
    assert AuthenticationService.PERM_USERS_VIEW in names


def test_seed_is_idempotent(session):
    first = seed_security_data(session)
    session.commit()
    permission_count = session.query(Permission).count()
    role_count = session.query(Role).count()

    second = seed_security_data(session)
    session.commit()

    assert second["permissions_added"] == 0
    assert second["roles_added"] == 0
    assert session.query(Permission).count() == permission_count
    assert session.query(Role).count() == role_count
    assert first["permissions_added"] > 0


def test_existing_administrator_role_receives_the_superuser_grant(session):
    old = Role(name="Administrator", description="Created by an old release")
    old.permissions.append(Permission(name="Inventory.*", description="Inventory"))
    session.add(old)
    session.commit()

    seed_security_data(session)
    session.commit()

    admin = session.query(Role).filter(Role.name == "Administrator").one()
    assert ".*" in {p.name for p in admin.permissions}


def test_existing_builtin_roles_receive_new_permissions_without_losing_old_ones(session):
    manager = Role(name="Manager", description="Existing manager")
    manager.permissions.append(Permission(name="Inventory.*", description="Inventory"))
    employee = Role(name="Employee", description="Existing employee")
    employee.permissions.append(
        Permission(name="CRM.Customers.View", description="Customers")
    )
    session.add_all([manager, employee])
    session.commit()

    seed_security_data(session)
    session.commit()

    manager_names = {
        p.name for p in session.query(Role).filter(Role.name == "Manager").one().permissions
    }
    employee_names = {
        p.name for p in session.query(Role).filter(Role.name == "Employee").one().permissions
    }
    assert set(MANAGER_PERMISSIONS) <= manager_names
    assert set(EMPLOYEE_PERMISSIONS) <= employee_names
    assert "CRM.Customers.View" in employee_names


def test_custom_role_permissions_are_never_removed(session):
    custom = Role(name="Accountant", description="Local customization")
    custom.permissions.append(Permission(name="Finance.Reports.View", description="Reports"))
    session.add(custom)
    session.commit()

    seed_security_data(session)
    session.commit()

    accountant = session.query(Role).filter(Role.name == "Accountant").one()
    assert "Finance.Reports.View" in {p.name for p in accountant.permissions}


def test_bootstrap_admin_is_created_once_with_the_factory_password(session):
    seed_security_data(session)
    assert ensure_bootstrap_admin(session) is True
    session.commit()

    assert ensure_bootstrap_admin(session) is False
    session.commit()

    admins = (
        session.query(User)
        .filter(User.role_id == session.query(Role)
                .filter(Role.name == "Administrator").one().id)
        .all()
    )
    assert len(admins) == 1
    assert AuthenticationService.verify_password(
        AuthenticationService.DEFAULT_ADMIN_PASSWORD, admins[0].password_hash
    )
    assert AuthenticationService.needs_first_run_setup(session=session) is True


def test_initialize_security_reports_what_it_did(session):
    report = initialize_security(session)
    session.commit()

    assert report["bootstrap_admin_created"] is True
    assert report["permissions_added"] == len(PERMISSION_DESCRIPTIONS)
    assert report["roles_added"] == 3
