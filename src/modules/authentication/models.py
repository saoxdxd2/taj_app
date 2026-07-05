from enum import Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Enum as SQLAlchemyEnum

from src.database.base import BaseModel

class Role(str, Enum):
    """
    User roles for Role-Based Access Control (RBAC).
    Defined in 15_SECURITY_STANDARD.md.
    """
    ADMINISTRATOR = "Administrator"
    MANAGER = "Manager"
    EMPLOYEE = "Employee"

class User(BaseModel):
    """
    Represents a system user.
    Passwords must be hashed using Argon2id before assignment.
    """
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(SQLAlchemyEnum(Role), nullable=False, default=Role.EMPLOYEE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
