import re
from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy import DateTime

def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

class BaseModel(DeclarativeBase):
    """
    Base model for all SQLAlchemy ORM models.
    Provides standard audit fields and automatic table naming.
    """
    __abstract__ = True

    # Automatic table name generation
    @classmethod
    def __declare_last__(cls):
        if not hasattr(cls, '__tablename__'):
            cls.__tablename__ = camel_to_snake(cls.__name__)

    # Standard fields for all models
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )
