"""
Tests for the configurable system settings (key/value store).

Verifies the fallback contract: an unset key returns its documented
default, a corrupt value falls back instead of crashing, and every write
is audited.
"""
import pytest

from src.modules.settings.services import SettingsService
from src.modules.settings.models import (
    SystemSetting, SettingKey, SETTING_DEFAULTS, SETTING_DESCRIPTIONS,
)
from src.modules.audit.models import AuditEvent
from src.security.permissions import AccessDenied


# --- Defaults -----------------------------------------------------------

def test_unset_setting_returns_documented_default(session, admin_context):
    """The migration seeds values, but the fallback must hold regardless."""
    for key, expected in SETTING_DEFAULTS.items():
        assert SettingsService.get_value(
            context=admin_context, session=session, key=key
        ) == expected


def test_defaults_reproduce_previous_hardcoded_values():
    """These numbers used to be literals in backup.py and logging.py."""
    assert SETTING_DEFAULTS[SettingKey.BACKUP_RETENTION_COUNT] == "15"
    assert SETTING_DEFAULTS[SettingKey.BACKUP_MIN_DISK_SPACE_MB] == "50"
    assert SETTING_DEFAULTS[SettingKey.LOG_ROTATION_SIZE_MB] == "10"
    assert SETTING_DEFAULTS[SettingKey.LOG_RETENTION_DAYS] == "30"
    assert SETTING_DEFAULTS[SettingKey.DEFAULT_WARRANTY_MONTHS] == "12"


def test_every_key_has_a_description():
    for key in SETTING_DEFAULTS:
        assert SETTING_DESCRIPTIONS.get(key)


# --- Round trip ---------------------------------------------------------

def test_set_value_then_read_it_back(session, admin_context):
    SettingsService.set_value(
        context=admin_context, session=session,
        key=SettingKey.BACKUP_RETENTION_COUNT, value="30",
    )
    assert SettingsService.get_int(
        context=admin_context, session=session, key=SettingKey.BACKUP_RETENTION_COUNT
    ) == 30


def test_set_value_updates_rather_than_duplicates(session, admin_context):
    """The key is the primary key, so a second write must update in place."""
    SettingsService.set_value(
        context=admin_context, session=session,
        key=SettingKey.LOG_RETENTION_DAYS, value="60",
    )
    SettingsService.set_value(
        context=admin_context, session=session,
        key=SettingKey.LOG_RETENTION_DAYS, value="90",
    )
    rows = session.query(SystemSetting).filter(
        SystemSetting.key == SettingKey.LOG_RETENTION_DAYS
    ).all()
    assert len(rows) == 1
    assert rows[0].value == "90"


def test_set_value_strips_whitespace(session, admin_context):
    SettingsService.set_value(
        context=admin_context, session=session,
        key=SettingKey.BACKUP_RETENTION_COUNT, value="  25  ",
    )
    assert SettingsService.get_int(
        context=admin_context, session=session, key=SettingKey.BACKUP_RETENTION_COUNT
    ) == 25


def test_get_all_settings_includes_every_key(session, admin_context):
    SettingsService.set_value(
        context=admin_context, session=session,
        key=SettingKey.INVOICE_NUMBER_PREFIX, value="FAC",
    )
    values = SettingsService.get_all_settings(context=admin_context, session=session)
    for key in SETTING_DEFAULTS:
        assert key in values
    assert values[SettingKey.INVOICE_NUMBER_PREFIX] == "FAC"

    assert values[SettingKey.INVOICE_NUMBER_PREFIX] == "FAC"


# --- Rejection ----------------------------------------------------------

def test_unknown_key_is_rejected(session, admin_context):
    with pytest.raises(ValueError, match="Unknown setting key"):
        SettingsService.set_value(
            context=admin_context, session=session,
            key="not.a.real.key", value="1",
        )


def test_empty_value_is_rejected(session, admin_context):
    with pytest.raises(ValueError, match="cannot be empty"):
        SettingsService.set_value(
            context=admin_context, session=session,
            key=SettingKey.BACKUP_RETENTION_COUNT, value="   ",
        )


def test_non_numeric_numeric_setting_is_rejected(session, admin_context):
    """A typo must be rejected instead of breaking the next startup."""
    with pytest.raises(ValueError, match="whole number"):
        SettingsService.set_value(
            context=admin_context, session=session,
            key=SettingKey.LOG_ROTATION_SIZE_MB, value="ten",
        )


def test_zero_or_negative_numeric_setting_is_rejected(session, admin_context):
    with pytest.raises(ValueError, match="at least 1"):
        SettingsService.set_value(
            context=admin_context, session=session,
            key=SettingKey.LOG_RETENTION_DAYS, value="0",
        )
    with pytest.raises(ValueError, match="at least 1"):
        SettingsService.set_value(
            context=admin_context, session=session,
            key=SettingKey.BACKUP_RETENTION_COUNT, value="-5",
        )


def test_numeric_setting_is_normalized(session, admin_context):
    SettingsService.set_value(
        context=admin_context, session=session,
        key=SettingKey.BACKUP_RETENTION_COUNT, value=" 025 ",
    )
    row = session.query(SystemSetting).filter(
        SystemSetting.key == SettingKey.BACKUP_RETENTION_COUNT
    ).one()
    assert row.value == "25"


# --- Corrupt values -----------------------------------------------------

def test_corrupt_int_value_falls_back_to_default(session, admin_context):
    """A hand-edited non-numeric value must not crash the caller."""
    # Simulate a row edited outside the service: set_value itself now
    # rejects this input. The migration may already have seeded the key.
    row = session.query(SystemSetting).filter(
        SystemSetting.key == SettingKey.LOG_ROTATION_SIZE_MB
    ).first()
    if row is None:
        row = SystemSetting(key=SettingKey.LOG_ROTATION_SIZE_MB)
        session.add(row)
    row.value = "not-a-number"
    session.commit()
    assert SettingsService.get_int(
        context=admin_context, session=session, key=SettingKey.LOG_ROTATION_SIZE_MB
    ) == 10  # the default


# --- Audit & permissions ------------------------------------------------

def test_set_value_is_audited_with_before_and_after(session, admin_context):
    SettingsService.set_value(
        context=admin_context, session=session,
        key=SettingKey.BACKUP_RETENTION_COUNT, value="20",
    )
    event = session.query(AuditEvent).filter(
        AuditEvent.action == "UPDATE_SYSTEM_SETTING"
    ).one()
    assert event.entity_name == "SystemSetting"
    assert event.entity_id == SettingKey.BACKUP_RETENTION_COUNT
    assert event.after_values["value"] == "20"
    # The first write reports the default as the previous value.
    assert event.before_values["value"] == SETTING_DEFAULTS[SettingKey.BACKUP_RETENTION_COUNT]


def test_second_write_audits_the_real_previous_value(session, admin_context):
    SettingsService.set_value(
        context=admin_context, session=session,
        key=SettingKey.BACKUP_RETENTION_COUNT, value="20",
    )
    SettingsService.set_value(
        context=admin_context, session=session,
        key=SettingKey.BACKUP_RETENTION_COUNT, value="21",
    )
    events = session.query(AuditEvent).filter(
        AuditEvent.action == "UPDATE_SYSTEM_SETTING"
    ).all()
    assert len(events) == 2
    assert any(e.before_values["value"] == "20" for e in events)


def test_updating_settings_requires_permission(session, unauthorized_context):
    with pytest.raises(AccessDenied):
        SettingsService.set_value(
            context=unauthorized_context, session=session,
            key=SettingKey.BACKUP_RETENTION_COUNT, value="5",
        )
