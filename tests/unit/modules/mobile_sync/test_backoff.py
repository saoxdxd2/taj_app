import httpx

from src.modules.mobile_sync.sync import (
    TERMINAL_CATEGORIES,
    SyncConfigError,
    categorize_error,
    compute_backoff,
    describe_error,
)


def _status_error(code):
    request = httpx.Request("GET", "https://relay.invalid/api/catalog")
    return httpx.HTTPStatusError("boom", request=request,
                                 response=httpx.Response(code, request=request, text="token=secret"))


def test_backoff_doubles_without_jitter_when_rng_is_centered():
    fixed = lambda: 0.5
    assert compute_backoff(0, base=5.0, rng=fixed) == 0.0
    assert compute_backoff(1, base=5.0, rng=fixed) == 5.0
    assert compute_backoff(2, base=5.0, rng=fixed) == 10.0
    assert compute_backoff(3, base=5.0, rng=fixed) == 20.0


def test_backoff_is_bounded_and_jitter_stays_within_range():
    assert compute_backoff(50, base=5.0, maximum=300.0, rng=lambda: 0.5) == 300.0
    assert compute_backoff(1, base=10.0, jitter_ratio=0.25, rng=lambda: 0.0) == 7.5
    assert compute_backoff(1, base=10.0, jitter_ratio=0.25, rng=lambda: 1.0) == 12.5
    assert compute_backoff(4, base=5.0, maximum=35.0, rng=lambda: 0.0) <= 35.0


def test_auth_config_conflict_are_terminal_and_transient_is_not():
    assert categorize_error(_status_error(401)) == "auth"
    assert categorize_error(_status_error(403)) == "auth"
    assert categorize_error(_status_error(404)) == "config"
    assert categorize_error(SyncConfigError("missing relay URL")) == "config"
    assert categorize_error(_status_error(409)) == "conflict"
    assert categorize_error(_status_error(503)) == "transient"
    assert categorize_error(httpx.ConnectError("offline")) == "transient"

    assert categorize_error(_status_error(401)) in TERMINAL_CATEGORIES
    assert categorize_error(_status_error(503)) not in TERMINAL_CATEGORIES


def test_error_description_never_includes_response_body():
    error = _status_error(500)
    description = describe_error(error)
    assert "secret" not in description
    assert "HTTP 500" in description
