import logging
from typing import Optional

from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional

logger = logging.getLogger(__name__)


class SettingsService:
    """
    Business service for application settings (company identity, etc.).
    """

    @staticmethod
    @transactional
    def get_company_settings(context: RequestContext, session):
        """
        Returns the singleton CompanySettings row, creating it with
        sensible defaults on first access.
        """
        PermissionManager.verify_permission(context, "Settings.Company.View")

        from src.modules.settings.models import CompanySettings
        settings = session.query(CompanySettings).filter(CompanySettings.id == 1).first()
        if not settings:
            settings = CompanySettings(id=1)
            session.add(settings)
            session.flush()
            logger.info("Initialized default company settings.")
        return settings

    @staticmethod
    @transactional
    def update_company_settings(context: RequestContext, session,
                                company_name: Optional[str] = None,
                                ice_number: Optional[str] = None,
                                rc_number: Optional[str] = None,
                                if_number: Optional[str] = None,
                                patente_number: Optional[str] = None,
                                cnss_number: Optional[str] = None,
                                address_street: Optional[str] = None,
                                address_city: Optional[str] = None,
                                phone: Optional[str] = None,
                                email: Optional[str] = None,
                                bank_name: Optional[str] = None,
                                bank_rib: Optional[str] = None,
                                invoice_footer_note: Optional[str] = None):
        """
        Updates the company identity printed on factures.
        Only provided (non-None) fields are changed.
        """
        PermissionManager.verify_permission(context, "Settings.Company.Update")

        settings = SettingsService.get_company_settings(context, session=session)

        before = {
            "company_name": settings.company_name,
            "ice_number": settings.ice_number,
        }

        fields = {
            "company_name": company_name,
            "ice_number": ice_number,
            "rc_number": rc_number,
            "if_number": if_number,
            "patente_number": patente_number,
            "cnss_number": cnss_number,
            "address_street": address_street,
            "address_city": address_city,
            "phone": phone,
            "email": email,
            "bank_name": bank_name,
            "bank_rib": bank_rib,
            "invoice_footer_note": invoice_footer_note,
        }
        for name, value in fields.items():
            if value is not None:
                setattr(settings, name, value.strip() if isinstance(value, str) else value)

        if not settings.company_name or not settings.company_name.strip():
            raise ValueError("Company name cannot be empty.")

        AuditService.record_event(
            session=session,
            action="UPDATE_COMPANY_SETTINGS",
            entity_name="CompanySettings",
            entity_id="1",
            before_values=before,
            after_values={"company_name": settings.company_name, "ice_number": settings.ice_number},
            user_id=context.user_id,
        )
        logger.info(f"Updated company settings by {context.username}.")
        return settings