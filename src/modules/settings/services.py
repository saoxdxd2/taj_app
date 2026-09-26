import logging
from typing import Optional, TYPE_CHECKING

from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional

# Imported only for type checking: the models are still imported lazily
# inside each method, preserving the existing runtime import order.
if TYPE_CHECKING:
    from src.modules.settings.models import CompanySettings, SystemSetting

logger = logging.getLogger(__name__)


class SettingsService:
    """
    Business service for application settings (company identity, etc.).
    """

    @staticmethod
    @transactional
    def get_company_settings(context: RequestContext, session) -> "CompanySettings":
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

    # ------------------------------------------------------------------
    # System settings (key/value, configurable instead of hardcoded)
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def get_value(context: RequestContext, session, key: str) -> str:
        """
        Returns the raw string value of a setting.

        Falls back to the documented default when the key has never been
        set, so callers never have to handle a missing setting.
        """
        from src.modules.settings.models import SystemSetting, SETTING_DEFAULTS
        setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting is not None:
            return setting.value
        return SETTING_DEFAULTS.get(key, "")

    @staticmethod
    @transactional
    def get_int(context: RequestContext, session, key: str) -> int:
        """
        Returns a setting as an integer, falling back to its default.

        A stored value that is not a valid integer (hand-edited or corrupted)
        falls back to the default and logs a warning rather than crashing the
        caller.
        """
        from src.modules.settings.models import SETTING_DEFAULTS
        raw = SettingsService.get_value(context=context, session=session, key=key)
        try:
            return int(raw)
        except (TypeError, ValueError):
            fallback = SETTING_DEFAULTS.get(key, "0")
            logger.warning(
                f"Setting '{key}' has non-integer value {raw!r}; "
                f"using default {fallback}."
            )
            try:
                return int(fallback)
            except (TypeError, ValueError):
                return 0

    @staticmethod
    @transactional
    def set_value(context: RequestContext, session, key: str, value: str) -> "SystemSetting":
        """
        Writes a system setting and records an audit event with the previous
        value, so no configuration change is ever silent.
        """
        from src.modules.settings.models import (
            SystemSetting, SETTING_DEFAULTS, SETTING_DESCRIPTIONS,
        )
        PermissionManager.verify_permission(context, "Settings.System.Update")

        if key not in SETTING_DEFAULTS:
            raise ValueError(
                f"Unknown setting key '{key}'. Known keys: {', '.join(sorted(SETTING_DEFAULTS))}"
            )

        value = "" if value is None else str(value).strip()
        if not value:
            raise ValueError(f"Setting '{key}' cannot be empty.")

        setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()
        before = setting.value if setting else SETTING_DEFAULTS.get(key)

        # RequestContext.user_id is a string; the column is an integer.
        try:
            updated_by = int(context.user_id) if context.user_id else None
        except (TypeError, ValueError):
            updated_by = None

        if setting is None:
            setting = SystemSetting(
                key=key,
                value=value,
                description=SETTING_DESCRIPTIONS.get(key),
                updated_by=updated_by,
            )
            session.add(setting)
        else:
            setting.value = value
            setting.updated_by = updated_by
        session.flush()

        AuditService.record_event(
            session=session,
            action="UPDATE_SYSTEM_SETTING",
            entity_name="SystemSetting",
            entity_id=key,
            before_values={"value": before},
            after_values={"value": value},
            user_id=context.user_id,
        )
        logger.info(f"Updated system setting '{key}' by {context.username}.")
        return setting

    @staticmethod
    @transactional
    def get_all_settings(context: RequestContext, session) -> dict:
        """
        Returns every known setting as {key: current_value}.

        Keys that have never been set are included with their default value,
        so the settings UI can display a complete picture.
        """
        from src.modules.settings.models import SystemSetting, SETTING_DEFAULTS
        stored = {
            row.key: row.value
            for row in session.query(SystemSetting).all()
        }
        defaults = dict(SETTING_DEFAULTS)
        defaults.update(stored)
        return defaults