from typing import Optional, Any
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, JSON

from src.database.base import BaseModel

class AuditEvent(BaseModel):
    """
    Represents an immutable record of a business or security event.
    Must never be edited or deleted.
    """
    __audit__ = False

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Store dynamic payloads safely
    before_values: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    after_values: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    
    # Context
    user_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
