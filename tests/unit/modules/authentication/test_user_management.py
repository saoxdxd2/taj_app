import pytest

from src.modules.authentication.services import AuthenticationService
from src.modules.authentication.models import User, Role


@pytest.fixture(autouse=True)
def seed_roles(session):
    """The app seeds roles at startup; tests must do the same."""
    for name in ("Administrator", "Manager", "Employee"):
        if not session.query(Role).filter(Role.name == name).first():
            session.add(Role(name=name))
    session.commit()


def test_create_user_persists_in_db(session):
    """Users are saved in the database and survive a fresh session."""
    AuthenticationService.create_user(session, "yassine", "secret123", "Manager")
    session.commit()

    # Fresh query in the same DB proves persistence
    user = session.query(User).filter(User.username == "yassine").first()
    assert user is not None
    assert user.role.name == "Manager"
    assert user.password_hash != "secret123"  # stored hashed, never plaintext


def test_create_user_rejects_duplicates(session):
    AuthenticationService.create_user(session, "dup", "password1", "Employee")
    with pytest.raises(ValueError, match="already exists"):
        AuthenticationService.create_user(session, "dup", "password2", "Employee")


def test_create_user_validates_password(session):
    with pytest.raises(ValueError, match="at least 8"):
        AuthenticationService.create_user(session, "shortpw", "abc", "Employee")


def test_list_users_returns_roles(session):
    AuthenticationService.create_user(session, "alice", "password1", "Administrator")
    users = AuthenticationService.list_users(session)
    alice = [u for u in users if u["username"] == "alice"]
    assert len(alice) == 1
    assert alice[0]["role"] == "Administrator"
    assert alice[0]["is_active"] is True


def test_set_user_active_disables_login(session):
    from src.core.context import RequestContext

    AuthenticationService.create_user(session, "bob", "password1", "Employee")
    session.commit()

    AuthenticationService.set_user_active(session, "bob", False)
    session.commit()

    result = AuthenticationService.authenticate_user(session, "bob", "password1")
    assert result is None  # disabled users cannot log in

    AuthenticationService.set_user_active(session, "bob", True)
    session.commit()
    result = AuthenticationService.authenticate_user(session, "bob", "password1")
    assert result is not None