from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean

from src.database.base import BaseModel

class Supplier(BaseModel):
    """
    Represents a supplier in the Suppliers domain.
    Follows the Soft Delete Policy (archived, never deleted).
    """
    company_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ice_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Identifiant Commun de l'Entreprise
    
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
