"""Checkpoint files can be truncated, corrupted or poisoned with secrets."""
import json

import pytest

from src.modules.mobile_sync import sync


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "mobile_sync_state.json"
    monkeypatch.setattr(sync, "STATE_FILE", path)
    return path


def test_corrupted_primary_checkpoint_recovers_from_backup(state_file):
    sync.save_state({
        "last_pulled_version": 3,
        "processed_scan_ids": ["scan-7"],
        "last_scan_id": "scan-7",
        "agentToken": "SECRET_TOKEN_DO_NOT_KEEP",
    })
    backup = sync._backup_path()
    assert backup.exists()

    # Simulate a partial/externally corrupted write (plus an injected secret).
    state_file.write_text(
        '{"last_scan_id":"scan-CORRUPT","token":"SECRET_TOKEN_DO_NOT_KEEP",',
        encoding="utf-8",
    )

    state = sync.load_state()
    assert state["last_pulled_version"] == 3
    assert state["last_scan_id"] == "scan-7"
    assert state["processed_scan_ids"] == ["scan-7"]
    assert "SECRET_TOKEN_DO_NOT_KEEP" not in repr(state)


def test_injected_secret_keys_are_dropped_on_load_and_on_save(state_file):
    state_file.write_text(json.dumps({
        "last_scan_id": "scan-1",
        "processed_scan_ids": ["scan-1"],
        "last_pulled_version": 5,
        "agentToken": "SECRET_TOKEN_DO_NOT_KEEP",
        "token": "SECRET_TOKEN_DO_NOT_KEEP",
        "authorization": "Bearer SECRET_TOKEN_DO_NOT_KEEP",
    }), encoding="utf-8")

    loaded = sync.load_state()
    assert "SECRET_TOKEN_DO_NOT_KEEP" not in repr(loaded)
    assert set(loaded) == {"last_scan_id", "processed_scan_ids", "last_pulled_version"}

    sync.save_state(loaded)
    saved = state_file.read_text(encoding="utf-8")
    assert "SECRET_TOKEN_DO_NOT_KEEP" not in saved
    assert json.loads(saved) == loaded


def test_unreadable_primary_and_backup_are_ignored_without_crash(state_file):
    state_file.write_text("{not-json", encoding="utf-8")
    backup = sync._backup_path()
    backup.write_text("[1, 2, 3]", encoding="utf-8")
    assert sync.load_state() == {}


def test_repeated_restarts_and_clock_skew_keep_boundary_sane(state_file):
    for index in range(20):
        scan_id = f"scan-{index}"
        sync.mark_scan_processed(scan_id)
        state = sync.load_state()
        assert state["last_scan_id"] == scan_id
        assert state["last_scan_id"] in state["processed_scan_ids"]
        assert isinstance(state["last_scan_id"], str)

        # A skewed clock or a poisoned boundary must not corrupt the checkpoint.
        raw = json.loads(state_file.read_text(encoding="utf-8"))
        raw["checkpoint_updated_at"] = "2099-01-01T00:00:00"
        raw["last_scan_id"] = {"token": "SECRET_TOKEN_DO_NOT_KEEP"}
        state_file.write_text(json.dumps(raw), encoding="utf-8")
        loaded = sync.load_state()
        assert "SECRET_TOKEN_DO_NOT_KEEP" not in repr(loaded)
        assert loaded["processed_scan_ids"] == state["processed_scan_ids"]
        assert "last_scan_id" not in loaded

        sync.save_state(state)

    final = sync.load_state()
    assert final["last_scan_id"] == "scan-19"
    assert sync.pending_scan_ids(
        [{"id": "scan-20"}, {"id": "scan-19"}]
    ) == [{"id": "scan-20"}]


def test_invalid_boundary_is_ignored_but_processed_ids_still_apply(state_file):
    sync.save_state({
        "processed_scan_ids": ["scan-1"],
        "last_scan_id": 42,
        "agentToken": "SECRET_TOKEN_DO_NOT_KEEP",
    })
    state = sync.load_state()
    assert "last_scan_id" not in state

    batch = [{"id": "scan-2"}, {"id": None}, {"id": "scan-1"}]
    assert sync.pending_scan_ids(batch) == [{"id": "scan-2"}]
