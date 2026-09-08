"""
TAJ FROID ERP - Authentication Endpoints
Complete authentication system with JWT tokens
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta

from src.api.core.database import get_async_session
from src.api.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token,
    Token, UserCreate, UserLogin, TokenData,
    get_current_user
)
from src.modules.authentication.models import User, Role

router = APIRouter()


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_async_session)):
    """Register a new user"""
    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    
    # Get roles
    roles = []
    for role_name in user_data.roles:
        result = await db.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if not role:
            role = Role(name=role_name)
            db.add(role)
        roles.append(role)
    
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        roles=roles
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return {
        "message": "User created successfully",
        "user_id": user.id,
        "username": user.username
    }


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_async_session)):
    """Login and get access token"""
    # Find user
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Create tokens
    token_data = {
        "sub": user.id,
        "username": user.username,
        "roles": [role.name for role in user.roles]
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.security.access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_async_session)):
    """Refresh access token using refresh token"""
    from src.api.core.security import decode_token, settings
    
    token_data = decode_token(refresh_token)
    if not token_data or token_data.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists or is disabled"
        )
    
    # Create new tokens
    new_token_data = {
        "sub": user.id,
        "username": user.username,
        "roles": [role.name for role in user.roles]
    }
    
    new_access_token = create_access_token(new_token_data)
    new_refresh_token = create_refresh_token(new_token_data)
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.security.access_token_expire_minutes * 60
    )


@router.get("/me", response_model=dict)
async def get_me(current_user: TokenData = Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    """Get current user information"""
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "roles": [role.name for role in user.roles],
        "is_active": user.is_active,
        "created_at": user.created_at
    }
