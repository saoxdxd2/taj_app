from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey, Enum as SQLAlchemyEnum

from src.database.base import BaseModel
from src.modules.parties import PartyType

class Customer(BaseModel):
    """
    Represents a customer in the CRM domain.
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
    ice_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Identifiant Commun de l'Entreprise (Morocco)
    
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    addresses: Mapped[List["Address"]] = relationship("Address", back_populates="customer", cascade="all, delete-orphan")

class Address(BaseModel):
    """
    Represents a physical address for a customer.
    """
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    street: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="Morocco", nullable=False)
    
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="addresses")
