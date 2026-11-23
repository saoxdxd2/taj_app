"""Status objects are safe to paste into a tray tooltip or Qt label."""
from src.modules.mobile_sync.sync import (
    VALID_ERROR_CATEGORIES,
    VALID_STATUS_STATES,
    SyncStatus,
)


def test_status_fields_are_always_valid_and_safe():
    status = SyncStatus(
        state="evil\nSECRET_TOKEN_DO_NOT_SHOW",
        last_sync_at="not-a-date",
        pending_in=-5,
        pending_out="SECRET_TOKEN_DO_NOT_SHOW",
        last_error_category="Bearer SECRET_TOKEN_DO_NOT_SHOW",
        consecutive_failures=-3,
    )
    data = status.to_dict()

    assert data["state"] in VALID_STATUS_STATES
    assert data["last_error_category"] is None
    assert data["last_sync_at"] is None
    assert data["pending_in"] == 0
    assert data["pending_out"] == 0
    assert data["consecutive_failures"] == 0
    assert "SECRET_TOKEN_DO_NOT_SHOW" not in status.compact()
    assert status.as_text() == status.compact()


def test_valid_status_values_are_preserved_and_snapshots_are_independent():
    status = SyncStatus(
        state="offline",
        last_sync_at="2026-01-02T03:04:05+00:00",
        pending_in=2,
        pending_out=1,
        last_error_category="transient",
        consecutive_failures=4,
    )
    snapshot = status.snapshot()
    assert snapshot == status
    assert "offline" in snapshot.compact()
    assert "transient" in snapshot.compact()
    assert "failures=4" in snapshot.compact()
    assert snapshot.last_error_category in VALID_ERROR_CATEGORIES

    snapshot.pending_in = 999
    snapshot.state = "invalid"
    assert status.pending_in == 2
    assert status.state == "offline"
