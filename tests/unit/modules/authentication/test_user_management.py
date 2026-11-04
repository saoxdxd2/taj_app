import pytest

from src.core.context import RequestContext
from src.modules.audit.models import AuditEvent
from src.modules.authentication.models import Role, User
from src.modules.authentication.services import AuthenticationService
from src.security.permissions import AccessDenied


@pytest.fixture(autouse=True)
def seed_roles(session):
    """The app seeds roles at startup; tests must do the same."""
    for name in ("Administrator", "Manager", "Employee"):
        if not session.query(Role).filter(Role.name == name).first():
            session.add(Role(name=name))
    session.commit()


def _make_user(session, admin_context, username="bob", password="Password1",
               role_name="Employee"):
    user = AuthenticationService.create_user(
        context=admin_context, session=session,
        username=username, password=password, role_name=role_name,
    )
    session.commit()
    return user


def _context_for(user, permissions=None):
    return RequestContext(
        user_id=str(user.id), username=user.username,
        role=user.role.name, permissions=permissions or set(),
    )


def test_create_user_persists_in_db(session, admin_context):
    """Users are saved in the database and survive a fresh session."""
    # Passwords must satisfy the complexity rule (upper, lower, digit, 8+).
    AuthenticationService.create_user(
        context=admin_context, session=session,
        username="yassine", password="Secret123", role_name="Manager",
    )
    session.commit()

    # Fresh query in the same DB proves persistence
    user = session.query(User).filter(User.username == "yassine").first()
    assert user is not None
    assert user.role.name == "Manager"
    assert user.password_hash != "Secret123"  # stored hashed


def test_create_user_rejects_duplicates(session, admin_context):
    _make_user(session, admin_context, username="dup")
    with pytest.raises(ValueError, match="already exists"):
        AuthenticationService.create_user(
            context=admin_context, session=session,
            username="dup", password="Password2", role_name="Employee",
        )


def test_create_user_validates_password(session, admin_context):
    with pytest.raises(ValueError, match="at least 8"):
        AuthenticationService.create_user(
            context=admin_context, session=session,
            username="shortpw", password="abc", role_name="Employee",
        )


def test_create_user_enforces_password_complexity(session, admin_context):
    """A long but weak password (no uppercase/digit) is still rejected."""
    with pytest.raises(ValueError, match="uppercase"):
        AuthenticationService.create_user(
            context=admin_context, session=session,
            username="weakpw", password="alllowercase", role_name="Employee",
        )


def test_create_user_requires_permission(session, unauthorized_context):
    with pytest.raises(AccessDenied):
        AuthenticationService.create_user(
            context=unauthorized_context, session=session,
            username="intruder", password="Password1", role_name="Employee",
        )


def test_non_admin_cannot_create_an_administrator(session):
    """A narrow Users.Create grant must not allow privilege escalation."""
    limited = RequestContext(
        user_id="9", username="manager", role="Manager",
        permissions={AuthenticationService.PERM_USERS_CREATE},
    )
    with pytest.raises(AccessDenied, match="administrator"):
        AuthenticationService.create_user(
            context=limited, session=session,
            username="eviladmin", password="Password1", role_name="Administrator",
        )


def test_list_users_returns_roles(session, admin_context):
    _make_user(session, admin_context, username="alice", role_name="Administrator")
    users = AuthenticationService.list_users(
        context=admin_context, session=session
    )
    alice = [u for u in users if u["username"] == "alice"]
    assert len(alice) == 1
    assert alice[0]["role"] == "Administrator"
    assert alice[0]["is_active"] is True


def test_list_users_requires_permission(session, unauthorized_context):
    with pytest.raises(AccessDenied):
        AuthenticationService.list_users(
            context=unauthorized_context, session=session
        )


def test_list_roles_returns_seeded_roles(session, admin_context):
    roles = AuthenticationService.list_roles(
        context=admin_context, session=session
    )
    assert {"Administrator", "Manager", "Employee"} <= set(roles)


def test_set_user_active_disables_login(session, admin_context):
    _make_user(session, admin_context, username="bob")

    AuthenticationService.set_user_active(
        context=admin_context, session=session,
        username="bob", is_active=False,
    )
    session.commit()

    result = AuthenticationService.authenticate_user(session, "bob", "Password1")
    assert result is None  # disabled users cannot log in

    AuthenticationService.set_user_active(
        context=admin_context, session=session,
        username="bob", is_active=True,
    )
    session.commit()
    result = AuthenticationService.authenticate_user(session, "bob", "Password1")
    assert result is not None


def test_set_user_active_requires_permission(session, admin_context,
                                             unauthorized_context):
    _make_user(session, admin_context, username="bob")
    with pytest.raises(AccessDenied):
        AuthenticationService.set_user_active(
            context=unauthorized_context, session=session,
            username="bob", is_active=False,
        )


def test_cannot_disable_your_own_account(session, admin_context):
    root = _make_user(
        session, admin_context, username="root", role_name="Administrator"
    )
    root_context = _context_for(root, permissions={"Everything"})

    with pytest.raises(ValueError, match="your own account"):
        AuthenticationService.set_user_active(
            context=root_context, session=session,
            username="root", is_active=False,
        )


def test_cannot_disable_the_last_active_administrator(session, admin_context):
    _make_user(
        session, admin_context, username="root", role_name="Administrator"
    )
    other_admin = RequestContext(
        user_id="2", username="other", role="Administrator",
        permissions={"Everything"},
    )

    with pytest.raises(ValueError, match="last active administrator"):
        AuthenticationService.set_user_active(
            context=other_admin, session=session,
            username="root", is_active=False,
        )


def test_self_service_password_change_requires_the_current_password(
    session, admin_context
):
    bob = _make_user(session, admin_context, username="bob")
    bob_context = _context_for(bob)

    with pytest.raises(ValueError, match="Current password"):
        AuthenticationService.change_password(
            context=bob_context, session=session,
            username="bob", new_password="NewStrong1",
        )

    with pytest.raises(ValueError, match="incorrect"):
        AuthenticationService.change_password(
            context=bob_context, session=session,
            username="bob", new_password="NewStrong1",
            current_password="WrongPass1",
        )

    assert AuthenticationService.change_password(
        context=bob_context, session=session,
        username="bob", new_password="NewStrong1",
        current_password="Password1",
    )
    assert AuthenticationService.authenticate_user(
        session, "bob", "NewStrong1"
    ) is not None


def test_administrator_can_reset_another_users_password(
    session, admin_context
):
    _make_user(session, admin_context, username="bob")
    assert AuthenticationService.change_password(
        context=admin_context, session=session,
        username="bob", new_password="ResetPass9",
    )
    assert AuthenticationService.authenticate_user(
        session, "bob", "ResetPass9"
    ) is not None


def test_change_password_requires_permission_for_another_user(
    session, admin_context, unauthorized_context
):
    _make_user(session, admin_context, username="bob")
    with pytest.raises(AccessDenied):
        AuthenticationService.change_password(
            context=unauthorized_context, session=session,
            username="bob", new_password="ResetPass9",
        )


def test_change_password_enforces_complexity_on_self(
    session, admin_context
):
    bob = _make_user(session, admin_context, username="bob")
    with pytest.raises(ValueError, match="uppercase"):
        AuthenticationService.change_password(
            context=_context_for(bob), session=session,
            username="bob", new_password="alllowercase1",
            current_password="Password1",
        )


def test_first_run_setup_replaces_the_factory_password_once(session):
    role = session.query(Role).filter(Role.name == "Administrator").first()
    session.add(User(
        username="admin",
        password_hash=AuthenticationService.hash_password("admin"),
        role_id=role.id,
    ))
    session.commit()

    assert AuthenticationService.needs_first_run_setup(session=session) is True

    saved_username = AuthenticationService.complete_first_run_setup(
        session=session, new_username="boss", new_password="NewStrong1"
    )
    session.commit()
    assert saved_username == "boss"
    assert AuthenticationService.needs_first_run_setup(session=session) is False

    # The old factory credentials no longer work, the new ones do.
    assert AuthenticationService.authenticate_user(session, "admin", "admin") is None
    assert AuthenticationService.authenticate_user(
        session, "boss", "NewStrong1"
    ) is not None

    # A second setup pass cannot replay the bootstrap operation.
    with pytest.raises(ValueError, match="already been completed"):
        AuthenticationService.complete_first_run_setup(
            session=session, new_username="other", new_password="NewStrong2"
        )


def test_corrupt_password_hash_fails_closed(session):
    role = session.query(Role).filter(Role.name == "Employee").first()
    session.add(User(
        username="corrupt",
        password_hash="this-is-not-an-argon2-hash",
        role_id=role.id,
    ))
    session.commit()

    assert AuthenticationService.verify_password("anything", "not-a-hash") is False
    assert AuthenticationService.authenticate_user(
        session, "corrupt", "anything"
    ) is None


def test_audit_trail_never_contains_password_hashes(session, admin_context):
    bob = _make_user(session, admin_context, username="bob")
    AuthenticationService.change_password(
        context=_context_for(bob), session=session,
        username="bob", new_password="NewStrong1",
        current_password="Password1",
    )
    session.commit()

    events = session.query(AuditEvent).filter(
        AuditEvent.entity_name == "User"
    ).all()
    assert events  # user creation and password change are audited
    for event in events:
        assert "password_hash" not in (event.before_values or {})
        assert "password_hash" not in (event.after_values or {})
