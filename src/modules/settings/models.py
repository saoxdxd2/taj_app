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


class SystemSetting(BaseModel):
    """
    A single configurable system value, stored as text.

    Exists so operational values (backup retention, log rotation, default
    warranty...) are configurable instead of hardcoded, while still living
    in the database next to the data they affect. Typed access is provided
    by SettingsService.get_int / get_str, which fall back to SETTING_DEFAULTS.

    `key` is the natural identifier and is unique, exactly like the SKU on a
    Product: `id` remains the immutable primary key, per the database standard.
    """
    __tablename__ = "system_setting"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Recorded as a plain indexed id (no foreign key), matching AuditEvent.user_id:
    # a settings row must survive the deletion of the user who last changed it,
    # and the audit trail already holds the authoritative record of the change.
    updated_by: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)


class SettingKey:
    """
    Canonical setting keys.

    These constants are the only supported way to read or write a system
    setting, so a typo is a NameError rather than a silently-ignored value.
    """
    BACKUP_RETENTION_COUNT = "backup.retention.count"
    BACKUP_MIN_DISK_SPACE_MB = "backup.disk_space.min_mb"
    LOG_ROTATION_SIZE_MB = "log.rotation.size_mb"
    LOG_RETENTION_DAYS = "log.retention.days"
    DEFAULT_WARRANTY_MONTHS = "sales.warranty.default_months"
    INVOICE_NUMBER_PREFIX = "sales.invoice.prefix"


# Fallbacks used whenever a key has never been set. These reproduce the
# values that were previously hardcoded, so behaviour is unchanged until an
# administrator edits a setting.
SETTING_DEFAULTS = {
    SettingKey.BACKUP_RETENTION_COUNT: "15",
    SettingKey.BACKUP_MIN_DISK_SPACE_MB: "50",
    SettingKey.LOG_ROTATION_SIZE_MB: "10",
    SettingKey.LOG_RETENTION_DAYS: "30",
    SettingKey.DEFAULT_WARRANTY_MONTHS: "12",
    SettingKey.INVOICE_NUMBER_PREFIX: "N°",
}

SETTING_DESCRIPTIONS = {
    SettingKey.BACKUP_RETENTION_COUNT: "How many database backups to keep on disk",
    SettingKey.BACKUP_MIN_DISK_SPACE_MB: "Minimum free disk space (MB) required before a backup runs",
    SettingKey.LOG_ROTATION_SIZE_MB: "Rotate the log file once it reaches this size (MB)",
    SettingKey.LOG_RETENTION_DAYS: "Delete rotated log files after this many days",
    SettingKey.DEFAULT_WARRANTY_MONTHS: "Default warranty applied to a new invoice line",
    SettingKey.INVOICE_NUMBER_PREFIX: "Prefix used when generating invoice numbers",
}