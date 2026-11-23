"""Relay batches are hostile input: normalize, bound, checkpoint safely."""
import httpx
import pytest

import src.modules.mobile_sync.inbox as inbox
from src.modules.mobile_sync import sync, worker


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "mobile_sync_state.json"
    monkeypatch.setattr(sync, "STATE_FILE", path)
    return path


class FakeClient:
    def __init__(self, batches):
        self.batches = list(batches)
        self.last_limit = None

    def list_uploaded_scans(self, limit=25):
        self.last_limit = limit
        if not self.batches:
            return []
        return self.batches.pop(0)

    def post_scan_status(self, *args, **kwargs):
        return {}


def _context():
    return object()


def test_malformed_scan_entries_are_dropped_and_unicode_ids_survive():
    batch = [
        {"name": "no id"},
        {"id": 123},
        {"id": None},
        {"id": {"nested": "SECRET"}},
        {"id": ["list"]},
        "not-a-dict",
        7,
        None,
        {"id": "scan-1"},
        {"id": "scan-1"},            # duplicate
        {"id": "扫描-١٢٣"},            # unicode is a valid opaque ID
        {"id": "../escape"},         # path traversal must not reach the inbox
        {"id": "nested/id"},
        {"id": "CON"},               # Windows-reserved file name
        {"id": ""},
        {"id": "has\ncontrol"},
    ]
    clean = sync.normalize_scans(batch)
    assert [scan["id"] for scan in clean] == ["scan-1", "扫描-١٢٣"]

    # A hostile relay can ignore the requested limit; the consumer still caps it.
    huge = [{"id": f"scan-{index}"} for index in range(5000)]
    assert len(sync.normalize_scans(huge, limit=7)) == 7
    assert len(sync.pending_scan_ids(huge, limit=7)) == 7


def test_engine_bounds_batch_and_skips_malformed_entries(state_file, monkeypatch):
    processed = []

    def fake_process(context, client, scan):
        processed.append(scan["id"])
        return object(), object()

    monkeypatch.setattr(inbox, "process_scan", fake_process)
    monkeypatch.setattr(worker, "_pending_out_count", lambda: 0)

    batch = [
        {"id": None},
        "junk",
        {"id": "scan-a"},
        {"id": "scan-a"},
        {"id": "扫描-b"},
        {"id": "scan-c"},
        {"id": "scan-d"},
    ]
    client = FakeClient([batch])
    engine = worker.SyncEngine(client, _context(), batch_size=3, poll_interval=0.0)

    assert engine.run_once() == 0.0
    assert client.last_limit == 3
    assert processed == ["scan-a", "扫描-b", "scan-c"]
    state = sync.load_state()
    assert state["last_scan_id"] == "scan-c"
    assert set(state["processed_scan_ids"]) == {"scan-a", "扫描-b", "scan-c"}


def test_older_scan_failure_does_not_advance_boundary_and_is_retried(state_file, monkeypatch):
    calls = []
    fail_ids = {"scan-1"}

    def fake_process(context, client, scan):
        relay_id = scan["id"]
        calls.append(relay_id)
        if relay_id in fail_ids:
            raise httpx.ConnectError("transient")
        return object(), object()

    monkeypatch.setattr(inbox, "process_scan", fake_process)
    monkeypatch.setattr(worker, "_pending_out_count", lambda: 0)

    # Relay order is newest first: scan-2 succeeds, then the older scan-1 fails.
    client = FakeClient([
        [{"id": "scan-2"}, {"id": "scan-1"}],
        [{"id": "scan-2"}, {"id": "scan-1"}],
    ])
    first = worker.SyncEngine(client, _context(), batch_size=10, poll_interval=0.25)

    assert first.run_once() == 0.25
    assert calls == ["scan-2", "scan-1"]

    state = sync.load_state()
    assert "scan-2" in state["processed_scan_ids"]
    assert "scan-1" not in state["processed_scan_ids"]
    assert "last_scan_id" not in state, "boundary must not skip the failed older scan"

    # Restart: only the failed scan is outstanding, and it is retried.
    fail_ids.clear()
    calls.clear()
    restarted = worker.SyncEngine(client, _context(), batch_size=10, poll_interval=0.25)
    assert restarted.run_once() == 0.25
    assert calls == ["scan-1"]

    state = sync.load_state()
    assert state["last_scan_id"] == "scan-1"
    assert set(state["processed_scan_ids"]) == {"scan-1", "scan-2"}


def test_duplicate_out_of_order_batch_respects_restart_boundary(state_file):
    sync.mark_scan_processed("scan-3")
    sync.set_scan_boundary("scan-3")

    batch = [
        {"id": "scan-4"},
        {"id": "scan-3"},
        {"id": "scan-4"},
        {"id": "scan-2"},   # behind the boundary: already processed in the past
    ]
    assert sync.pending_scan_ids(batch) == [{"id": "scan-4"}]
