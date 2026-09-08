"""
TAJ FROID ERP - Security & Authentication
JWT-based authentication with role-based access control
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

from src.api.core.settings import settings


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class Token(BaseModel):
    """JWT Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token payload data"""
    user_id: Optional[int] = None
    username: Optional[str] = None
    roles: list[str] = Field(default_factory=list)


class UserCreate(BaseModel):
    """User creation schema"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=100)
    roles: list[str] = Field(default_factory=lambda: ["user"])


class UserLogin(BaseModel):
    """Login credentials"""
    username: str
    password: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.security.access_token_expire_minutes))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.security.secret_key, algorithm=settings.security.algorithm)


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.security.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.security.secret_key, algorithm=settings.security.algorithm)


def decode_token(token: str) -> Optional[TokenData]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, settings.security.secret_key, algorithms=[settings.security.algorithm])
        user_id: int = payload.get("sub")
        username: str = payload.get("username")
        roles: list = payload.get("roles", [])
        
        if user_id is None:
            return None
        
        return TokenData(user_id=user_id, username=username, roles=roles)
    except JWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    user_data = decode_token(token)
    if user_data is None:
        raise credentials_exception
    
    return user_data


async def require_role(required_role: str):
    """Dependency factory to require specific role"""
    async def role_checker(current_user: TokenData = Depends(get_current_user)):
        if required_role not in current_user.roles and "admin" not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return current_user
    return role_checker


def require_admin():
    """Require admin role"""
    async def admin_checker(current_user: TokenData = Depends(get_current_user)):
        if "admin" not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return current_user
    return admin_checker
