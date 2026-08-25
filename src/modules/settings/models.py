from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from src.database.base import BaseModel


class CompanySettings(BaseModel):
    """
    Singleton row (id = 1) holding the legal identity of the business,
    printed on every facture. Moroccan invoice fields included:
    ICE, RC, IF, Patente.
    """
    company_name: Mapped[str] = mapped_column(String(150), nullable=False, default="TAJ FROID")
    ice_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rc_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)      # Registre de Commerce
    if_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)      # Identifiant Fiscal
    patente_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cnss_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    address_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_rib: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Footer note printed on factures (e.g. payment terms / warranty)
    invoice_footer_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)