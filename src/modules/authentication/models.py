from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Table, Column, ForeignKey

from src.database.base import BaseModel

# Association table for Many-to-Many relationship between Role and Permission
role_permission_table = Table(
    "role_permission",
    BaseModel.metadata,
    Column("role_id", ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True),
)

class Permission(BaseModel):
    """
    Represents a granular permission or wildcard (e.g., 'Inventory.Products.Create' or 'Inventory.*').
    """
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

class Role(BaseModel):
    """
    User roles for Role-Based Access Control (RBAC).
    """
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Relationships
    permissions: Mapped[List[Permission]] = relationship(
        secondary=role_permission_table,
        lazy="joined" # Eagerly load permissions when a role is loaded
    )

class User(BaseModel):
    """
    Represents a system user.
    Passwords must be hashed using Argon2id before assignment.
    """
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("role.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    role: Mapped[Role] = relationship(lazy="joined")
