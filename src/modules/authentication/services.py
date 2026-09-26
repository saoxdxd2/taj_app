import logging
import datetime
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from src.modules.authentication.models import User, Role
from src.security.sanitizers import validate_password_strength, sanitize_username

from src.database.transaction import transactional

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
        """
        try:
            return ph.verify(hashed_password, password)
        except VerifyMismatchError:
            return False

    @staticmethod
    @transactional
    def authenticate_user(session, username: str, password: str) -> User | None:
        """
        Authenticates a user by username and password.
        Returns the User object if successful and active, otherwise None.

        Repeated failures lock the account temporarily; a successful
        attempt clears the counter. The username is never written to the
        log, so the auth log cannot be used to enumerate accounts.
        """
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
        logger.info(f"Authentication successful for user '{username}'.")
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
        import uuid
        import datetime

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
            correlation_id=str(uuid.uuid4()),
            workstation=workstation,
            language=language,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        CurrentSession.initialize(context)
        return True

    @staticmethod
    @transactional
    def change_password(session, username: str, new_password: str) -> bool:
        """
        Changes the password for a given user.
        The new password is hashed with Argon2id before storage.
        Returns True if successful.
        """
        if not new_password or len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        validate_password_strength(new_password)
        
        user = session.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError(f"User '{username}' not found.")
        
        user.password_hash = AuthenticationService.hash_password(new_password)
        session.flush()
        logger.info(f"Password changed successfully for user '{username}'.")
        return True

    @staticmethod
    @transactional
    def is_default_password(session, username: str) -> bool:
        """
        Returns True if the user still has the factory-default 'admin' password.
        Used to trigger the first-run setup wizard.
        """
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return False
        return AuthenticationService.verify_password("admin", user.password_hash)

    @staticmethod
    @transactional
    def create_user(session, username: str, password: str, role_name: str) -> User:
        """
        Creates a new user with a hashed password and an existing role.
        Users are persisted in the SQLite database like everything else.
        """
        if not username or not username.strip():
            raise ValueError("Username is required.")
        username = sanitize_username(username)
        if not username:
            raise ValueError("Username is required.")
        validate_password_strength(password)

        if session.query(User).filter(User.username == username).first():
            raise ValueError(f"User '{username}' already exists.")

        role = session.query(Role).filter(Role.name == role_name).first()
        if not role:
            raise ValueError(f"Role '{role_name}' does not exist.")

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
    def list_users(session) -> list:
        """
        Returns all users with their role names, for the management UI.
        """
        users = session.query(User).all()
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
    def set_user_active(session, username: str, is_active: bool) -> bool:
        """Enables or disables a user account."""
        user = session.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError(f"User '{username}' not found.")
        user.is_active = is_active
        logger.info(f"User '{username}' {'enabled' if is_active else 'disabled'}.")
        return True

    @staticmethod
    def logout():
        """
        Clears the active session.
        """
        from src.core.session import CurrentSession
        CurrentSession.clear()
        logger.info("User logged out successfully.")
