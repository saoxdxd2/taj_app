import logging
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from src.modules.authentication.models import User, Role

# Initialize the Argon2id password hasher
# Argon2id is the preferred algorithm defined in 15_SECURITY_STANDARD.md
ph = PasswordHasher()

logger = logging.getLogger(__name__)

class AuthenticationService:
    """
    Business service handling authentication and authorization logic.
    Provides secure password hashing and verification.
    """
    
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
    def authenticate_user(session, username: str, password: str) -> User | None:
        """
        Authenticate a user by username and password.
        Returns the User object if successful and active, otherwise None.
        """
        user = session.query(User).filter(User.username == username).first()
        
        if not user:
            logger.info("Authentication failed: User not found.")
            return None
            
        if not user.is_active:
            logger.info(f"Authentication failed: User '{username}' is deactivated.")
            return None
            
        if not AuthenticationService.verify_password(password, user.password_hash):
            logger.info(f"Authentication failed: Invalid password for user '{username}'.")
            return None
            
        logger.info(f"Authentication successful for user '{username}'.")
        return user
