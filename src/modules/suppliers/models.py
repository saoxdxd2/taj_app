from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Integer, Enum as SQLAlchemyEnum

from src.database.base import BaseModel
from src.modules.parties import PartyType

class Supplier(BaseModel):
    """
    Represents a supplier in the Suppliers domain.
    Follows the Soft Delete Policy (archived, never deleted).
    """
    party_type: Mapped[PartyType] = mapped_column(
        SQLAlchemyEnum(PartyType), default=PartyType.ENTERPRISE, nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Individuals have no company; their full name is also stored in
    # company_name so every list and document keeps a single display name.
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ice_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Identifiant Commun de l'Entreprise
    
    # Agreed payment terms in days (0 = cash on delivery, 30/60/90 = à terme)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
