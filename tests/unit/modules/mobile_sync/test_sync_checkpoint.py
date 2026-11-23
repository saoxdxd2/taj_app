import json

import pytest

from src.modules.mobile_sync import sync


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "mobile_sync_state.json"
    monkeypatch.setattr(sync, "STATE_FILE", path)
    return path


def test_save_state_is_atomic_and_stores_only_checkpoint_metadata(state_file):
    sync.save_state({
        "last_pulled_version": 7,
        "agentToken": "do-not-persist",
        "authorization": "Bearer do-not-persist",
    })
    assert json.loads(state_file.read_text(encoding="utf-8")) == {"last_pulled_version": 7}
    assert list(state_file.parent.glob("*.tmp")) == []


def test_failed_replace_keeps_previous_checkpoint_and_removes_temp(state_file, monkeypatch):
    sync.save_state({"last_pulled_version": 3})
    original = state_file.read_bytes()

    def boom(*_args, **_kwargs):
        raise OSError("simulated os.replace failure")

    monkeypatch.setattr(sync.os, "replace", boom)
    sync.save_state({"last_pulled_version": 9})

    assert state_file.read_bytes() == original
    assert list(state_file.parent.glob("*.tmp")) == []


def test_malformed_state_is_ignored(state_file):
    state_file.write_text("{not-json", encoding="utf-8")
    assert sync.load_state() == {}


def test_processed_scan_checkpoint_is_durable_and_bounded(state_file):
    total = sync.MAX_PROCESSED_IDS + 5
    for index in range(total):
        sync.mark_scan_processed(f"scan-{index}")

    state = sync.load_state()
    assert len(state["processed_scan_ids"]) == sync.MAX_PROCESSED_IDS
    assert state["processed_scan_ids"][-1] == f"scan-{total - 1}"
    assert state["last_scan_id"] == f"scan-{total - 1}"
    assert state["checkpoint_updated_at"]

    # Restart scenario: the durable boundary skips everything already read.
    batch = [{"id": "scan-new"}, {"id": f"scan-{total - 1}"}]
    assert sync.pending_scan_ids(batch) == [{"id": "scan-new"}]


def test_boundary_is_not_advanced_past_a_failed_scan(state_file):
    sync.mark_scan_processed("scan-1")
    # scan-2 failed and was not checkpointed; scan-3 succeeded but must not
    # move the cursor past the failure.
    sync.mark_scan_processed("scan-3", advance_boundary=False)

    assert sync.load_state()["last_scan_id"] == "scan-1"
    batch = [{"id": "scan-3"}, {"id": "scan-2"}, {"id": "scan-1"}]
    assert sync.pending_scan_ids(batch) == [{"id": "scan-2"}]
