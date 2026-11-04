"""Authentication, user management and brute-force protection.

The service layer is the security boundary: every operation that touches
another user's account verifies a permission on the caller's
:class:`RequestContext`. The UI only decides what to show; it cannot grant
access by calling a service method directly.
"""
import datetime
import logging
import secrets
from typing import List, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from src.core.context import RequestContext
from src.database.transaction import transactional
from src.modules.audit.services import AuditService
from src.modules.authentication.models import Role, User
from src.security.permissions import AccessDenied, PermissionManager
from src.security.sanitizers import sanitize_username, validate_password_strength

# Initialize the Argon2id password hasher
# Argon2id is the preferred algorithm defined in 15_SECURITY_STANDARD.md
ph = PasswordHasher()

logger = logging.getLogger(__name__)


class AuthenticationService:
    """
    Business service handling authentication and authorization logic.
    Provides secure password hashing and verification.
    """

    # --- Brute-force protection ---
    # Consecutive failures before the account is temporarily locked, and the
    # lock duration for each subsequent failure.
    MAX_FAILED_LOGINS = 5
    LOCKOUT_STEPS_SECONDS = (60, 300, 900, 3600)
    MAX_LOCKOUT_SECONDS = 3600 * 24

    # --- Authorization ---
    # Keep the permission names in one place: they are seeded in main.py and
    # checked by the methods below.
    PERM_USERS_VIEW = "Security.Users.View"
    PERM_USERS_CREATE = "Security.Users.Create"
    PERM_USERS_UPDATE = "Security.Users.Update"

    ADMIN_ROLE = "Administrator"
    DEFAULT_ADMIN_PASSWORD = "admin"

    @staticmethod
    def _require(context: Optional[RequestContext], permission: str) -> None:
        """
        Fails closed when no context is supplied.

        A service call without a RequestContext must never be treated as an
        implicit administrator call.
        """
        if context is None:
            raise AccessDenied("Authentication is required for this operation.")
        PermissionManager.verify_permission(context, permission)

    @staticmethod
    def _is_superuser(context: Optional[RequestContext]) -> bool:
        """True when the context carries an unrestricted permission grant."""
        if context is None:
            return False
        return bool({"Everything", ".*"} & set(context.permissions or ()))

    @staticmethod
    def _audit_user_id(context: Optional[RequestContext]) -> Optional[int]:
        """Converts the string context user id to the integer audit column."""
        if context is None or not context.user_id:
            return None
        try:
            return int(context.user_id)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Passwords
    # ------------------------------------------------------------------

    @classmethod
    def _register_failed_login(cls, user: User) -> None:
        """
        Records a failed attempt and locks the account once the threshold
        is reached. The lockout grows with each further failure, capped so
        a forgotten password cannot lock an account out indefinitely.
        """
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count < cls.MAX_FAILED_LOGINS:
            return

        step_index = user.failed_login_count - cls.MAX_FAILED_LOGINS
        if step_index >= len(cls.LOCKOUT_STEPS_SECONDS):
            seconds = cls.MAX_LOCKOUT_SECONDS
        else:
            seconds = cls.LOCKOUT_STEPS_SECONDS[step_index]

        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        user.locked_until = now + datetime.timedelta(seconds=seconds)
        logger.warning(
            f"Account locked for {seconds}s after {user.failed_login_count} "
            "consecutive failed logins."
        )

    @staticmethod
    def _is_locked_out(user: User) -> bool:
        """
        True when the account is currently locked. An expired lock is
        cleared on the spot so the next attempt is evaluated normally.
        """
        if user.locked_until is None:
            return False
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        if user.locked_until > now:
            return True
        # The lock has expired: clear it and let this attempt through.
        user.locked_until = None
        user.failed_login_count = 0
        return False

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a plaintext password using Argon2id.
        """
        if not password:
            raise ValueError("Password cannot be empty.")
        return ph.hash(password)

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify a plaintext password against an Argon2id hash.

        A corrupt or truncated hash fails closed: it is treated as a
        mismatch instead of raising out of the login path and crashing the
        application. Hashes are never included in the log message.
        """
        if not hashed_password:
            return False
        try:
            return ph.verify(hashed_password, password)
        except VerifyMismatchError:
            return False
        except (InvalidHashError, VerificationError, ValueError, TypeError) as exc:
            logger.warning(
                "Password verification failed: stored hash is invalid (%s).",
                type(exc).__name__,
            )
            return False

    # ------------------------------------------------------------------
    # Login / logout
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def authenticate_user(session, username: str, password: str) -> Optional[User]:
        """
        Authenticates a user by username and password.
        Returns the User object if successful and active, otherwise None.

        Repeated failures lock the account temporarily; a successful
        attempt clears the counter. The username is never written to the
        log, so the auth log cannot be used to enumerate accounts.
        """
        username = sanitize_username(username)
        user = session.query(User).filter(User.username == username).first()

        if not user:
            # Deliberately identical to the "locked" message: revealing
            # which accounts exist would let an attacker enumerate usernames.
            logger.info("Authentication failed: unknown user or bad credentials.")
            return None

        if not user.is_active:
            logger.info("Authentication failed: account is deactivated.")
            return None

        if AuthenticationService._is_locked_out(user):
            logger.warning(
                "Authentication refused: account is temporarily locked out."
            )
            return None

        if not AuthenticationService.verify_password(password, user.password_hash):
            AuthenticationService._register_failed_login(user)
            session.flush()
            logger.info("Authentication failed: invalid credentials.")
            return None

        # Success: clear the lockout state.
        user.failed_login_count = 0
        user.locked_until = None
        logger.info("Authentication successful.")
        return user

    @staticmethod
    @transactional
    def login(session, username: str, password: str, workstation: str = "Unknown", language: str = "en") -> bool:
        """
        Authenticates a user and initializes CurrentSession.
        Returns True if successful, False otherwise.
        """
        from src.core.session import CurrentSession
        from src.core.context import RequestContext

        user = AuthenticationService.authenticate_user(session, username, password)
        if not user:
            return False

        # Resolve permissions dynamically from the database
        permissions = {p.name for p in user.role.permissions}

        context = RequestContext(
            user_id=str(user.id),
            username=user.username,
            role=user.role.name,
            permissions=permissions,
            workstation=workstation,
            language=language,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        CurrentSession.initialize(context)
        return True

    @staticmethod
    def logout() -> None:
        """
        Clears the active session.
        """
        from src.core.session import CurrentSession
        CurrentSession.clear()
        logger.info("User logged out successfully.")

    # ------------------------------------------------------------------
    # First-run bootstrap (runs before there is a logged-in context)
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def is_default_password(session, username: str) -> bool:
        """
        Returns True if the user still has the factory-default 'admin' password.
        Used to trigger the first-run setup wizard.
        """
        user = (
            session.query(User)
            .filter(User.username == sanitize_username(username))
            .first()
        )
        if not user:
            return False
        return AuthenticationService.verify_password(
            AuthenticationService.DEFAULT_ADMIN_PASSWORD, user.password_hash
        )

    @staticmethod
    @transactional
    def needs_first_run_setup(session) -> bool:
        """
        True while an Administrator account still uses the factory password.

        Checked by role rather than username, because the setup wizard
        renames the account.
        """
        role = (
            session.query(Role)
            .filter(Role.name == AuthenticationService.ADMIN_ROLE)
            .first()
        )
        if role is None:
            return False
        admins = session.query(User).filter(User.role_id == role.id).all()
        return any(
            AuthenticationService.verify_password(
                AuthenticationService.DEFAULT_ADMIN_PASSWORD, user.password_hash
            )
            for user in admins
        )

    @staticmethod
    @transactional
    def complete_first_run_setup(session, new_username: str, new_password: str) -> str:
        """
        Replaces the factory administrator credentials.

        This is intentionally callable without a RequestContext: it runs
        before anyone can log in. It is replay-safe because it only acts on
        an Administrator account that still has the factory password; once
        the password has been changed it refuses to run again.

        Returns the normalized username that was saved.
        """
        role = (
            session.query(Role)
            .filter(Role.name == AuthenticationService.ADMIN_ROLE)
            .first()
        )
        if role is None:
            raise ValueError("Administrator role is missing; the database is not initialized.")

        admins = session.query(User).filter(User.role_id == role.id).all()
        default_admins = [
            user for user in admins
            if AuthenticationService.verify_password(
                AuthenticationService.DEFAULT_ADMIN_PASSWORD, user.password_hash
            )
        ]
        if not default_admins:
            raise ValueError("First-run setup has already been completed.")

        username = sanitize_username(new_username)
        if not username:
            raise ValueError("Username is required.")
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters long.")
        validate_password_strength(new_password)
        if AuthenticationService.verify_password(
            new_password, default_admins[0].password_hash
        ):
            raise ValueError("The new password must be different from the default password.")

        existing = (
            session.query(User)
            .filter(User.username == username, User.id != default_admins[0].id)
            .first()
        )
        if existing:
            raise ValueError(f"User '{username}' already exists.")

        admin = default_admins[0]
        admin.username = username
        admin.password_hash = AuthenticationService.hash_password(new_password)
        admin.failed_login_count = 0
        admin.locked_until = None
        # The bootstrap account must be usable after setup, even if an older
        # database left the factory administrator deactivated.
        admin.is_active = True

        # Defensive: a database seeded by an older version could contain
        # more than one factory-password administrator. Secure the others
        # so a second setup pass cannot be replayed on them.
        for other in default_admins[1:]:
            other.is_active = False
            other.password_hash = AuthenticationService.hash_password(
                secrets.token_urlsafe(32)
            )
            logger.warning(
                "Deactivated an additional administrator account that still "
                "used the factory password."
            )

        session.flush()
        AuditService.record_event(
            session=session,
            action="FIRST_RUN_SETUP",
            entity_name="User",
            entity_id=str(admin.id),
            after_values={"username": username},
        )
        logger.info("First-run setup completed for the administrator account.")
        return username

    # ------------------------------------------------------------------
    # User management (authorized)
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def change_password(context: RequestContext, session, username: str,
                        new_password: str,
                        current_password: Optional[str] = None) -> bool:
        """
        Changes a user's password.

        Self-service changes require the current password, even when the
        caller holds the user-management permission. Resetting somebody
        else's password requires ``Security.Users.Update``. The new
        password is hashed with Argon2id before storage.
        """
        user = (
            session.query(User)
            .filter(User.username == sanitize_username(username))
            .first()
        )
        if not user:
            raise ValueError(f"User '{username}' not found.")

        is_self = bool(
            context and context.username == user.username
        )

        if is_self:
            if not current_password:
                raise ValueError(
                    "Current password is required to change your own password."
                )
            if not AuthenticationService.verify_password(
                current_password, user.password_hash
            ):
                raise ValueError("Current password is incorrect.")
        else:
            AuthenticationService._require(context, AuthenticationService.PERM_USERS_UPDATE)
            if (
                user.role
                and user.role.name == AuthenticationService.ADMIN_ROLE
                and not AuthenticationService._is_superuser(context)
            ):
                raise AccessDenied(
                    "Only an administrator can reset another administrator's password."
                )

        validate_password_strength(new_password)

        user.password_hash = AuthenticationService.hash_password(new_password)
        # A password reset also clears any lockout caused by guessing.
        user.failed_login_count = 0
        user.locked_until = None
        session.flush()

        AuditService.record_event(
            session=session,
            action="CHANGE_PASSWORD",
            entity_name="User",
            entity_id=str(user.id),
            user_id=AuthenticationService._audit_user_id(context),
        )
        logger.info("Password changed successfully.")
        return True

    @staticmethod
    @transactional
    def create_user(context: RequestContext, session, username: str,
                    password: str, role_name: str) -> User:
        """
        Creates a new user with a hashed password and an existing role.
        Users are persisted in the SQLite database like everything else.
        """
        AuthenticationService._require(context, AuthenticationService.PERM_USERS_CREATE)

        username = sanitize_username(username)
        if not username:
            raise ValueError("Username is required.")
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters long.")
        validate_password_strength(password)

        role = session.query(Role).filter(Role.name == role_name).first()
        if not role:
            raise ValueError(f"Role '{role_name}' does not exist.")

        # Creating another administrator is privilege escalation unless the
        # caller already is one.
        if (
            role.name == AuthenticationService.ADMIN_ROLE
            and not AuthenticationService._is_superuser(context)
        ):
            raise AccessDenied("Only an administrator can create an administrator account.")

        if session.query(User).filter(User.username == username).first():
            raise ValueError(f"User '{username}' already exists.")

        user = User(
            username=username,
            password_hash=AuthenticationService.hash_password(password),
            role_id=role.id,
        )
        session.add(user)
        session.flush()
        logger.info(f"Created user '{username}' with role '{role_name}'.")
        return user

    @staticmethod
    @transactional
    def list_users(context: RequestContext, session) -> List[dict]:
        """
        Returns all users with their role names, for the management UI.
        """
        AuthenticationService._require(context, AuthenticationService.PERM_USERS_VIEW)
        users = session.query(User).order_by(User.username).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role.name if u.role else "-",
                "is_active": bool(u.is_active),
            }
            for u in users
        ]

    @staticmethod
    @transactional
    def list_roles(context: RequestContext, session) -> List[str]:
        """Returns the assignable role names, for the user-creation dialog."""
        AuthenticationService._require(context, AuthenticationService.PERM_USERS_VIEW)
        return [role.name for role in session.query(Role).order_by(Role.name).all()]

    @staticmethod
    @transactional
    def set_user_active(context: RequestContext, session, username: str,
                        is_active: bool) -> bool:
        """
        Enables or disables a user account.

        Two lockout guards protect the system: an administrator cannot
        disable their own account, and the last active administrator
        cannot be disabled. Both would otherwise leave nobody able to
        administer the ERP.
        """
        AuthenticationService._require(context, AuthenticationService.PERM_USERS_UPDATE)

        user = (
            session.query(User)
            .filter(User.username == sanitize_username(username))
            .first()
        )
        if not user:
            raise ValueError(f"User '{username}' not found.")

        is_self = bool(context and context.username == user.username)
        target_is_admin = bool(
            user.role and user.role.name == AuthenticationService.ADMIN_ROLE
        )
        if target_is_admin and not AuthenticationService._is_superuser(context):
            raise AccessDenied(
                "Only an administrator can enable or disable an administrator account."
            )

        if not is_active and user.is_active:
            if is_self:
                raise ValueError("You cannot disable your own account.")
            if target_is_admin:
                other_admins = (
                    session.query(User)
                    .filter(
                        User.role_id == user.role_id,
                        User.is_active.is_(True),
                        User.id != user.id,
                    )
                    .count()
                )
                if other_admins == 0:
                    raise ValueError(
                        "Cannot disable the last active administrator."
                    )

        user.is_active = is_active
        session.flush()
        logger.info(f"User '{user.username}' {'enabled' if is_active else 'disabled'}.")
        return True
