"""Catalog pushes carry an optimistic-concurrency base revision.

An offline desktop must not overwrite a newer relay catalog and leave phones
on a stale 304 response. The relay sends 409 with the current revision; the
desktop adopts it and retries once with the same snapshot.
"""
import httpx
import pytest

from src.modules.mobile_sync import catalog, sync


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "mobile_sync_state.json"
    monkeypatch.setattr(sync, "STATE_FILE", path)
    return path


def _conflict(current_revision):
    request = httpx.Request("PUT", "https://relay.invalid/api/agent/catalog")
    response = httpx.Response(409, json={"currentRevision": current_revision}, request=request)
    return httpx.HTTPStatusError("conflict", request=request, response=response)


class FakeClient:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def push_catalog(self, version, products, base_revision=0):
        self.calls.append(base_revision)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def fake_payload(monkeypatch):
    monkeypatch.setattr(
        catalog, "build_catalog_payload",
        lambda context, base_revision=0: {
            "version": 99,
            "baseRevision": int(base_revision),
            "products": [{"sku": "A", "name": "A"}],
        },
    )


def test_stale_catalog_push_retries_with_current_revision(
    state_file, fake_payload, monkeypatch,
):
    sync.save_state({"last_pushed_revision": 5})
    client = FakeClient([_conflict(42), {"revision": 43}])

    result = sync.push_catalog(object(), client)

    assert client.calls == [5, 42]
    assert result == {"revision": 43}
    state = sync.load_state()
    assert state["last_pushed_revision"] == 43
    assert state["last_pushed_version"] == 99
    assert state["last_pushed_at"]


def test_malformed_conflict_does_not_retry_or_advance_checkpoint(
    state_file, fake_payload, monkeypatch,
):
    sync.save_state({"last_pushed_revision": 5})
    request = httpx.Request("PUT", "https://relay.invalid/api/agent/catalog")
    bad = httpx.HTTPStatusError(
        "conflict", request=request,
        response=httpx.Response(409, text="not json", request=request),
    )
    client = FakeClient([bad])

    with pytest.raises(httpx.HTTPStatusError):
        sync.push_catalog(object(), client)

    assert client.calls == [5]
    assert sync.load_state()["last_pushed_revision"] == 5


def test_explicit_base_revision_overrides_state(
    state_file, fake_payload, monkeypatch,
):
    sync.save_state({"last_pushed_revision": 5})
    client = FakeClient([{"revision": 11}])

    sync.push_catalog(object(), client, base_revision=10)

    assert client.calls == [10]
    assert sync.load_state()["last_pushed_revision"] == 11
