"""
Tests for login lockout (brute-force protection).

The properties under test: repeated failures lock the account, a correct
password is refused while locked, and a successful login clears the
counter so a user is not punished for one typo.
"""
import pytest
from datetime import datetime, timedelta, timezone

from src.modules.authentication.services import AuthenticationService
from src.modules.authentication.models import User, Role


@pytest.fixture(autouse=True)
def seed_roles(session):
    for name in ("Administrator", "Manager", "Employee"):
        if not session.query(Role).filter(Role.name == name).first():
            session.add(Role(name=name))
    session.commit()


def _make_user(session, username="bob", password="Password1"):
    AuthenticationService.create_user(session, username, password, "Employee")
    session.commit()
    return session.query(User).filter(User.username == username).first()


def _utcnow():
    """
    Naive UTC 'now'.

    The `locked_until` column is a naive DateTime and the service stores
    naive UTC, so the test must compare against the same representation.
    _utcnow() is deprecated; this is the supported equivalent.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Lockout ------------------------------------------------------------

def test_account_locks_after_repeated_failures(session):
    user = _make_user(session)
    limit = AuthenticationService.MAX_FAILED_LOGINS

    for _ in range(limit - 1):
        assert AuthenticationService.authenticate_user(
            session, "bob", "WrongPass1"
        ) is None

    # The threshold attempt is the one that locks.
    assert AuthenticationService.authenticate_user(session, "bob", "WrongPass1") is None
    session.commit()

    user = session.query(User).filter(User.username == "bob").first()
    assert user.locked_until is not None
    assert user.locked_until > _utcnow()


def test_correct_password_is_refused_while_locked(session):
    """
    This is the whole point: brute force must not succeed once locked.
    """
    user = _make_user(session)
    limit = AuthenticationService.MAX_FAILED_LOGINS
    for _ in range(limit):
        AuthenticationService.authenticate_user(session, "bob", "WrongPass1")
    session.commit()

    assert AuthenticationService.authenticate_user(session, "bob", "Password1") is None


def test_lockout_expires_and_allows_login(session):
    """An expired lock must not lock the user out permanently."""
    user = _make_user(session)
    limit = AuthenticationService.MAX_FAILED_LOGINS
    for _ in range(limit):
        AuthenticationService.authenticate_user(session, "bob", "WrongPass1")
    session.commit()

    user = session.query(User).filter(User.username == "bob").first()
    # Simulate the lock having expired in the past.
    user.locked_until = _utcnow() - timedelta(minutes=1)
    session.commit()

    result = AuthenticationService.authenticate_user(session, "bob", "Password1")
    assert result is not None


def test_successful_login_clears_the_failure_counter(session):
    """One typo must not count against the user after a later success."""
    user = _make_user(session)
    AuthenticationService.authenticate_user(session, "bob", "WrongPass1")
    session.commit()

    user = session.query(User).filter(User.username == "bob").first()
    assert user.failed_login_count == 1

    result = AuthenticationService.authenticate_user(session, "bob", "Password1")
    session.commit()
    assert result is not None

    user = session.query(User).filter(User.username == "bob").first()
    assert user.failed_login_count == 0
    assert user.locked_until is None


def test_lockout_is_per_account(session):
    """One user's failures must not lock a different user out."""
    _make_user(session, "bob")
    _make_user(session, "carol", "Password2")

    limit = AuthenticationService.MAX_FAILED_LOGINS
    for _ in range(limit):
        AuthenticationService.authenticate_user(session, "bob", "WrongPass1")
    session.commit()

    # Carol is unaffected.
    assert AuthenticationService.authenticate_user(
        session, "carol", "Password2"
    ) is not None


def test_lockout_backoff_grows_then_caps(session):
    """Lockout duration increases with repeated failures, but is capped."""
    user = _make_user(session)
    for _ in range(AuthenticationService.MAX_FAILED_LOGINS):
        AuthenticationService.authenticate_user(session, "bob", "WrongPass1")

    first = user.locked_until
    assert first is not None

    # Clear and repeat to observe a longer lockout.
    user.locked_until = None
    for _ in range(AuthenticationService.MAX_FAILED_LOGINS + 2):
        AuthenticationService.authenticate_user(session, "bob", "WrongPass1")

    second = user.locked_until
    assert second > first
    assert (second - _utcnow()).total_seconds() <= \
        AuthenticationService.MAX_LOCKOUT_SECONDS


# --- Password change ----------------------------------------------------

def test_change_password_enforces_complexity(session):
    _make_user(session)
    with pytest.raises(ValueError, match="uppercase"):
        AuthenticationService.change_password(session, "bob", "alllowercase1")


def test_change_password_accepts_a_strong_password(session):
    _make_user(session)
    assert AuthenticationService.change_password(session, "bob", "NewStrong1")
    assert AuthenticationService.authenticate_user(session, "bob", "NewStrong1")
