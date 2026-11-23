"""Desktop <-> relay synchronization helpers.

Push: send the current ERP catalog to the relay (PUT /api/agent/catalog).
Pull: fetch the relay catalog snapshot (GET /api/catalog) for review.
Merge policy is deliberately conservative for Phase 0: pulled changes are
returned to the caller as a diff; nothing is written to the local DB
automatically. Automatic merging comes later, with per-field versioning.

The on-disk state is a *checkpoint* only: version cursors, timestamps and
processed relay scan IDs. Tokens, ciphertext and scan contents are never
written here, and unexpected keys are dropped on read and on write.
"""
from __future__ import annotations

import json
import logging
import os
import random
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from src.core.paths import CONFIG_DIR

logger = logging.getLogger(__name__)

STATE_FILE = CONFIG_DIR / "mobile_sync_state.json"

# Only non-secret checkpoint metadata is ever persisted. Anything else
# (including a token accidentally passed by a caller) is ignored.
CHECKPOINT_KEYS = frozenset({
    "last_pushed_version",
    "last_pushed_at",
    "last_pulled_version",
    "last_pulled_at",
    "processed_scan_ids",
    "last_scan_id",
    "checkpoint_updated_at",
})
MAX_PROCESSED_IDS = 500

# Backoff defaults; callers may override for tests or different transports.
BASE_BACKOFF = 5.0
MAX_BACKOFF = 300.0
JITTER_RATIO = 0.25

# Categories that must not be retried in a loop: the operator has to fix
# credentials/configuration, or review the conflict first.
TERMINAL_CATEGORIES = frozenset({"auth", "config", "conflict"})

_state_lock = threading.RLock()


class SyncConfigError(RuntimeError):
    """Local configuration/credential problem; never retry in a tight loop."""


@dataclass
class SyncStatus:
    """Small, log-safe snapshot of the background sync loop.

    ``state`` is one of: idle, syncing, offline, conflict, error.
    ``last_error_category`` uses the vocabulary from :func:`categorize_error`.
    """

    state: str = "idle"
    last_sync_at: Optional[str] = None
    pending_in: int = 0
    pending_out: int = 0
    last_error_category: Optional[str] = None
    consecutive_failures: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def snapshot(self) -> "SyncStatus":
        return SyncStatus(**self.to_dict())

    def compact(self) -> str:
        failures = f", failures={self.consecutive_failures}" if self.consecutive_failures else ""
        category = f", last={self.last_error_category}" if self.last_error_category else ""
        return f"{self.state} (in={self.pending_in}, out={self.pending_out}{failures}{category})"

    # Backwards-friendly alias used by the Qt status signal.
    def as_text(self) -> str:
        return self.compact()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON via temp file + fsync + atomic replace.

    A crash or an error mid-write leaves the previous checkpoint intact and
    never leaves a half-written state file behind.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _clean_checkpoint(state: Dict[str, Any]) -> Dict[str, Any]:
    clean = {key: value for key, value in state.items() if key in CHECKPOINT_KEYS}
    dropped = set(state) - CHECKPOINT_KEYS
    if dropped:
        logger.warning("Dropped %d non-checkpoint key(s) from mobile sync state.", len(dropped))
    return clean


def load_state() -> Dict[str, Any]:
    with _state_lock:
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            logger.warning("Mobile sync state is not an object; ignoring it.")
            return {}
        return _clean_checkpoint(data)


def save_state(state: Dict[str, Any]) -> None:
    with _state_lock:
        try:
            _atomic_write_json(STATE_FILE, _clean_checkpoint(state))
        except OSError as exc:
            logger.warning("Could not save mobile sync state: %s", exc)


def mark_scan_processed(scan_id: Any, advance_boundary: bool = True) -> None:
    """Atomically record one relay scan as processed (oldest IDs evicted).

    ``advance_boundary`` must be False when an earlier scan in the same batch
    failed; otherwise a later success would move the cursor past the failed
    scan and it would never be retried.
    """
    rid = str(scan_id)
    with _state_lock:
        state = load_state()
        ids = [str(value) for value in state.get("processed_scan_ids", []) if value]
        if rid in ids:
            return
        ids.append(rid)
        state["processed_scan_ids"] = ids[-MAX_PROCESSED_IDS:]
        if advance_boundary:
            state["last_scan_id"] = rid
        state["checkpoint_updated_at"] = _now_iso()
        save_state(state)


def pending_scan_ids(scans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter a relay batch against the durable checkpoint (no re-processing).

    The relay returns scans in a stable order (newest first), so
    ``last_scan_id`` acts as a resume boundary: only items before it are new.
    Processed IDs are kept as a second guard in case that order changes.
    """
    state = load_state()
    processed = {str(value) for value in state.get("processed_scan_ids", [])}
    boundary = state.get("last_scan_id")
    ordered = list(scans)
    if boundary:
        index = next(
            (i for i, scan in enumerate(ordered) if str(scan.get("id")) == str(boundary)),
            None,
        )
        if index is not None:
            ordered = ordered[:index]
    return [scan for scan in ordered if scan.get("id") and str(scan["id"]) not in processed]


def compute_backoff(
    consecutive_failures: int,
    base: float = BASE_BACKOFF,
    maximum: float = MAX_BACKOFF,
    jitter_ratio: float = JITTER_RATIO,
    rng: Callable[[], float] = random.random,
) -> float:
    """Bounded exponential backoff with symmetric jitter.

    With ``rng=0.5`` (or a fixed 0.5 callable) there is no jitter, which makes
    the calculation deterministic in tests. The result never exceeds
    ``maximum`` and is never negative.
    """
    if consecutive_failures <= 0:
        return 0.0
    exponent = min(base * (2 ** (consecutive_failures - 1)), maximum)
    jitter = 1.0 + jitter_ratio * (2.0 * rng() - 1.0)
    return min(maximum, max(0.0, exponent * jitter))


def describe_error(exc: BaseException) -> str:
    """Log-safe error label: type + HTTP status only, never bodies/tokens."""
    status_code = getattr(exc, "status_code", None)
    if status_code is None and isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
    if status_code is not None:
        return f"{type(exc).__name__}(HTTP {status_code})"
    return type(exc).__name__


def categorize_error(exc: BaseException) -> str:
    """Map an exception to a retry category without inspecting payloads."""
    if isinstance(exc, SyncConfigError):
        return "config"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return "auth"
        if code == 409:
            return "conflict"
        if code in (408, 429, 500, 502, 503, 504):
            return "transient"
        if 400 <= code < 500:
            return "config"
        return "transient"
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError, OSError)):
        return "transient"
    return "error"


def push_catalog(context, client, version: Optional[int] = None) -> Dict[str, Any]:
    from .catalog import build_catalog_payload
    payload = build_catalog_payload(context)
    if version is not None:
        payload["version"] = version
    result = client.push_catalog(payload["version"], payload["products"])
    state = load_state()
    state["last_pushed_version"] = payload["version"]
    state["last_pushed_at"] = _now_iso()
    save_state(state)
    logger.info("Pushed catalog version %s (%s products).", payload["version"], len(payload["products"]))
    return result


def pull_catalog(client, since_version: int = 0) -> Tuple[int, List[Dict[str, Any]]]:
    """Pull one catalog batch; 304 means the checkpoint is still current."""
    data = client.get_catalog(since_version)
    if data is None:  # HTTP 304
        return since_version, []
    new_version = int(data.get("version", since_version))
    products = data.get("products", [])
    state = load_state()
    state["last_pulled_version"] = new_version
    state["last_pulled_at"] = _now_iso()
    save_state(state)
    return new_version, products


def diff_catalog(local_products: List[Dict[str, Any]], remote_products: List[Dict[str, Any]]) -> Dict[str, List]:
    """Simple SKU-keyed diff: added / removed / changed (price/stock)."""
    local = {p["sku"]: p for p in local_products}
    remote = {p["sku"]: p for p in remote_products}
    added = [p for sku, p in remote.items() if sku not in local]
    removed = [p for sku, p in local.items() if sku not in remote]
    changed = []
    for sku in local.keys() & remote.keys():
        if local[sku] != remote[sku]:
            changed.append({"sku": sku, "local": local[sku], "remote": remote[sku]})
    return {"added": added, "removed": removed, "changed": changed}
