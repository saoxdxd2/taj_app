"""Relay response failures stay bounded, log-safe and status-safe."""
import logging

import httpx
import pytest

from src.modules.mobile_sync import client as client_module
from src.modules.mobile_sync import sync, worker
from src.modules.mobile_sync.client import RelayClient

SECRET = "SECRET_TOKEN_DO_NOT_LOG"
REQUEST = httpx.Request("GET", "https://relay.invalid/api/catalog")


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "mobile_sync_state.json"
    monkeypatch.setattr(sync, "STATE_FILE", path)
    return path


@pytest.fixture
def fake_httpx(monkeypatch):
    class FakeResponse:
        def __init__(self, body=b"", status_code=200, headers=None):
            self.status_code = status_code
            self.content = body if isinstance(body, bytes) else body.encode("utf-8")
            self.headers = headers or {}
            self.request = REQUEST
            self.url = REQUEST.url
            self.reason_phrase = "Fake"

        def raise_for_status(self):
            if 400 <= self.status_code < 600:
                raise httpx.HTTPStatusError(
                    "relay error", request=self.request, response=self,
                )

    class FakeHTTPXClient:
        queue = []
        calls = []

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def _next(self, method, url, kwargs):
            self.calls.append((method, url, kwargs))
            if not self.queue:
                raise AssertionError("FakeHTTPXClient has no queued response")
            return self.queue.pop(0)

        def get(self, url, **kwargs):
            return self._next("GET", url, kwargs)

        def post(self, url, **kwargs):
            return self._next("POST", url, kwargs)

        def put(self, url, **kwargs):
            return self._next("PUT", url, kwargs)

    FakeHTTPXClient.queue = []
    FakeHTTPXClient.calls = []
    monkeypatch.setattr(client_module.httpx, "Client", FakeHTTPXClient)
    return FakeHTTPXClient, FakeResponse


class RaisingClient:
    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0

    def list_uploaded_scans(self, limit=25):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return []


def _status_error(code):
    return httpx.HTTPStatusError(
        "relay error", request=REQUEST,
        response=httpx.Response(code, request=REQUEST, text=f"Bearer {SECRET}"),
    )


@pytest.mark.parametrize("body,content_type", [
    (f"<html>{SECRET}</html>", "text/html"),
    (f"{{not-json: {SECRET}", "application/json"),
    ("", "application/json"),
    ("plain text " + SECRET, "text/plain"),
])
def test_bad_relay_bodies_are_reported_safely(
    state_file, fake_httpx, monkeypatch, caplog, body, content_type,
):
    fake_class, FakeResponse = fake_httpx
    fake_class.queue.append(FakeResponse(body, headers={"content-type": content_type}))
    monkeypatch.setattr(worker, "_pending_out_count", lambda: 0)

    client = RelayClient("https://relay.invalid", token=SECRET)
    engine = worker.SyncEngine(client, object(), poll_interval=0.0)

    with caplog.at_level(logging.DEBUG):
        delay = engine.run_once()

    snapshot = engine.get_status().to_dict()
    assert delay is not None and delay > 0
    assert snapshot["state"] == "offline"
    assert snapshot["last_error_category"] == "transient"
    assert snapshot["consecutive_failures"] == 1
    assert SECRET not in caplog.text
    assert SECRET not in repr(snapshot)


def test_oversized_body_is_rejected_without_leaking_content(
    state_file, fake_httpx, monkeypatch, caplog,
):
    fake_class, FakeResponse = fake_httpx
    monkeypatch.setattr(client_module, "MAX_RESPONSE_BYTES", 64)
    fake_class.queue.append(FakeResponse(f"x" * 65 + SECRET))

    client = RelayClient("https://relay.invalid", token=SECRET)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(sync.RelayResponseError):
            client.list_uploaded_scans()
    assert SECRET not in caplog.text


def test_304_and_empty_json_bodies_are_handled(fake_httpx):
    fake_class, FakeResponse = fake_httpx
    client = RelayClient("https://relay.invalid", token=SECRET)

    fake_class.queue.append(FakeResponse(b"", status_code=304))
    assert client.get_catalog(5) is None

    fake_class.queue.append(FakeResponse(b"", status_code=304))
    assert sync.pull_catalog(client, 5) == (5, [])

    fake_class.queue.append(FakeResponse(b"", status_code=304))
    assert client.list_uploaded_scans() == []

    fake_class.queue.append(FakeResponse(b""))
    assert client.push_catalog(1, []) == {}

    fake_class.queue.append(FakeResponse(b""))
    assert client.heartbeat() == {}


def test_first_401_stops_the_loop_with_auth_status(state_file, monkeypatch):
    raising = RaisingClient([_status_error(401)])
    monkeypatch.setattr(worker, "RelayClient", lambda *args, **kwargs: raising)

    tray_worker = worker.TraySyncWorker("https://relay.invalid", object())
    tray_worker.run()  # terminal: returns instead of tight-looping

    status = tray_worker.get_status().to_dict()
    assert raising.calls == 1
    assert status["state"] == "error"
    assert status["last_error_category"] == "auth"
    assert SECRET not in repr(status)


def test_409_maps_to_conflict_status(state_file):
    engine = worker.SyncEngine(RaisingClient([_status_error(409)]), object())
    assert engine.run_once() is None
    status = engine.get_status().to_dict()
    assert status["state"] == "conflict"
    assert status["last_error_category"] == "conflict"


def test_5xx_uses_bounded_backoff(state_file):
    engine = worker.SyncEngine(
        RaisingClient([_status_error(503) for _ in range(25)]),
        object(), poll_interval=0.0,
    )
    delays = []
    for _ in range(25):
        delay = engine.run_once()
        assert delay is not None
        assert 0 < delay <= sync.MAX_BACKOFF
        delays.append(delay)

    status = engine.get_status().to_dict()
    assert status["state"] == "offline"
    assert status["last_error_category"] == "transient"
    assert status["consecutive_failures"] == 25
    assert delays[-1] <= sync.MAX_BACKOFF
