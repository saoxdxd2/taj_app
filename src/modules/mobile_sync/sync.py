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
import math
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


def _backup_path(path: Any = None) -> Path:
    """Backup path derived at call time (tests swap ``STATE_FILE`` freely)."""
    primary = Path(STATE_FILE if path is None else path)
    return primary.with_name(primary.name + ".bak")

# Only non-secret checkpoint metadata is ever persisted. Anything else
# (including a token accidentally passed by a caller) is ignored.
CHECKPOINT_KEYS = frozenset({
    "last_pushed_version",
    "last_pushed_revision",
    "last_pushed_at",
    "last_pulled_version",
    "last_pulled_at",
    "processed_scan_ids",
    "last_scan_id",
    "checkpoint_updated_at",
})
MAX_PROCESSED_IDS = 500
MAX_SCAN_ID_LENGTH = 128
MAX_BATCH_ITEMS = 1000

# Backoff defaults; callers may override for tests or different transports.
BASE_BACKOFF = 5.0
MAX_BACKOFF = 300.0
JITTER_RATIO = 0.25

# Categories that must not be retried in a loop: the operator has to fix
# credentials/configuration, or review the conflict first.
TERMINAL_CATEGORIES = frozenset({"auth", "config", "conflict"})

# Status surfaces (tray tooltip, Qt label) only ever render these values.
VALID_STATUS_STATES = frozenset({"idle", "syncing", "offline", "conflict", "error"})
VALID_ERROR_CATEGORIES = frozenset({"auth", "config", "conflict", "transient", "error"})

# Windows rejects these as file names; relay IDs are also used as inbox paths.
_WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})

_state_lock = threading.RLock()


class SyncConfigError(RuntimeError):
    """Local configuration/credential problem; never retry in a tight loop."""


class RelayResponseError(RuntimeError):
    """Relay returned an unusable payload (HTML, bad JSON, empty, huge).

    Messages are deliberately generic: response bodies may contain secrets or
    ciphertext and must never reach logs or status objects.
    """


def safe_text(value: Any, limit: int = 200) -> str:
    """Control-character-free, bounded text for logs/UI/relay status fields."""
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float)):
        text = str(value)
    else:
        return ""
    cleaned = "".join(ch if ch.isprintable() else " " for ch in text)
    cleaned = " ".join(cleaned.split())
    return cleaned[:max(0, int(limit))]


# Alias kept for callers that prefer the private-looking spelling from older code.
_safe_text = safe_text


def normalize_scan_id(value: Any) -> Optional[str]:
    """Return a safe relay scan ID, or None for anything unusable.

    IDs are opaque strings: integers, ``None``, containers, control characters
    and path separators are rejected instead of being coerced. Unicode IDs are
    preserved as-is (after trimming), so non-ASCII relay identifiers work.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or len(candidate) > MAX_SCAN_ID_LENGTH:
        return None
    if any(not ch.isprintable() for ch in candidate):
        return None
    if candidate in (".", "..") or "/" in candidate or "\\" in candidate:
        return None
    if candidate.upper() in _WINDOWS_RESERVED_NAMES:
        return None
    return candidate


# Friendly aliases for external callers/tests.
sanitize_scan_id = normalize_scan_id
_sanitize_scan_id = normalize_scan_id


def normalize_scans(scans: Any, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Sanitize, deduplicate and bound one relay batch.

    The relay can return non-dict entries, numeric/null IDs, repeated IDs and
    far more items than requested. Only the first ``limit`` unique, valid
    entries survive, in the order supplied by the relay (newest first).
    """
    if scans is None:
        return []
    if isinstance(scans, dict):
        try:
            candidates: Any = scans.get("scans", [])
        except Exception:  # noqa: BLE001 - hostile mapping
            return []
    elif isinstance(scans, (list, tuple)):
        candidates = scans
    else:
        return []

    if limit is None:
        cap = MAX_BATCH_ITEMS
    else:
        try:
            cap = max(0, int(limit))
        except (TypeError, ValueError, OverflowError):
            cap = MAX_BATCH_ITEMS
        cap = min(cap, MAX_BATCH_ITEMS)

    result: List[Dict[str, Any]] = []
    seen = set()
    for item in candidates:
        if len(result) >= cap:
            break
        if not isinstance(item, dict):
            continue
        try:
            rid = normalize_scan_id(item.get("id"))
        except Exception:  # noqa: BLE001 - hostile mapping
            rid = None
        if rid is None or rid in seen:
            continue
        seen.add(rid)
        clean = dict(item)
        clean["id"] = rid
        result.append(clean)
    return result


sanitize_scans = normalize_scans


def _safe_iso(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 64 or any(not ch.isprintable() for ch in text):
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return text


def _nonneg_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0, number)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON via temp file + fsync + atomic replace.

    A crash or an error mid-write leaves the previous checkpoint intact and
    never leaves a half-written state file behind. A ``.bak`` copy of the last
    good checkpoint is kept so an externally corrupted file can be recovered.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = _backup_path(path)

    # Snapshot the current good checkpoint before touching the primary file.
    try:
        existing = path.read_bytes()
        if isinstance(json.loads(existing.decode("utf-8")), dict):
            backup.write_bytes(existing)
    except (OSError, ValueError, UnicodeError):
        pass

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

    # Keep the backup current; a failure here is never fatal to the save.
    try:
        backup.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def _clean_checkpoint(state: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    clean: Dict[str, Any] = {}
    for key in CHECKPOINT_KEYS:
        if key not in state:
            continue
        value = state[key]
        if key in ("last_pushed_version", "last_pushed_revision", "last_pulled_version"):
            number = _nonneg_int(value)
            if number is not None:
                clean[key] = number
        elif key == "processed_scan_ids":
            if isinstance(value, (list, tuple)):
                ids: List[str] = []
                seen = set()
                for item in value:
                    rid = normalize_scan_id(item)
                    if rid is None or rid in seen:
                        continue
                    ids.append(rid)
                    seen.add(rid)
                if ids:
                    clean[key] = ids[-MAX_PROCESSED_IDS:]
        elif key == "last_scan_id":
            rid = normalize_scan_id(value)
            if rid:
                clean[key] = rid
        else:  # timestamp keys
            timestamp = _safe_iso(value)
            if timestamp:
                clean[key] = timestamp

    # A boundary that does not point at a checkpointed scan is unsafe: it
    # could skip scans that were never processed (e.g. an injected token).
    boundary = clean.get("last_scan_id")
    processed = clean.get("processed_scan_ids", [])
    if boundary and boundary not in processed:
        clean.pop("last_scan_id", None)

    dropped = set(state) - CHECKPOINT_KEYS
    if dropped:
        # Never log key names or values: either may carry an injected secret.
        logger.warning("Dropped %d non-checkpoint key(s) from mobile sync state.", len(dropped))
    return clean


def load_state() -> Dict[str, Any]:
    with _state_lock:
        data = _read_json_file(STATE_FILE)
        if not isinstance(data, dict):
            backup = _read_json_file(_backup_path())
            if isinstance(backup, dict):
                logger.warning("Mobile sync checkpoint was unreadable; using the backup copy.")
                data = backup
            else:
                if data is not None:
                    logger.warning("Mobile sync checkpoint is not an object; ignoring it.")
                return {}
        return _clean_checkpoint(data)


def save_state(state: Dict[str, Any]) -> None:
    with _state_lock:
        clean = _clean_checkpoint(state)
        try:
            _atomic_write_json(STATE_FILE, clean)
        except OSError as exc:
            logger.warning("Could not save mobile sync state: %s", describe_error(exc))


def _checkpoint_ids(state: Dict[str, Any]) -> List[str]:
    values = state.get("processed_scan_ids", [])
    if not isinstance(values, (list, tuple)):
        return []
    ids: List[str] = []
    seen = set()
    for item in values:
        rid = normalize_scan_id(item)
        if rid is None or rid in seen:
            continue
        ids.append(rid)
        seen.add(rid)
    return ids


def mark_scan_processed(scan_id: Any, advance_boundary: bool = True) -> None:
    """Atomically record one relay scan as processed (oldest IDs evicted).

    ``advance_boundary`` must be False while an earlier scan in the same batch
    may still fail; otherwise a later success would move the cursor past the
    failed scan and it would never be retried. The worker records successes
    with ``advance_boundary=False`` and calls :func:`set_scan_boundary` only
    after the entire batch succeeds.
    """
    rid = normalize_scan_id(scan_id)
    if rid is None:
        logger.warning("Ignoring a malformed relay scan ID in the checkpoint.")
        return
    with _state_lock:
        state = load_state()
        ids = _checkpoint_ids(state)
        if rid in ids:
            return
        ids.append(rid)
        state["processed_scan_ids"] = ids[-MAX_PROCESSED_IDS:]
        if advance_boundary:
            state["last_scan_id"] = rid
        state["checkpoint_updated_at"] = _now_iso()
        save_state(state)


def set_scan_boundary(scan_id: Any) -> None:
    """Move the resume boundary only after a whole batch has succeeded."""
    rid = normalize_scan_id(scan_id)
    if rid is None:
        return
    with _state_lock:
        state = load_state()
        ids = _checkpoint_ids(state)
        if rid not in ids:
            ids.append(rid)
        state["processed_scan_ids"] = ids[-MAX_PROCESSED_IDS:]
        state["last_scan_id"] = rid
        state["checkpoint_updated_at"] = _now_iso()
        save_state(state)


def pending_scan_ids(scans: Any, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Filter a relay batch against the durable checkpoint (no re-processing).

    The relay returns scans in a stable order (newest first), so
    ``last_scan_id`` acts as a resume boundary: only items before it are new.
    Processed IDs are kept as a second guard in case that order changes.
    """
    ordered = normalize_scans(scans, limit=limit)
    state = load_state()
    processed = set(_checkpoint_ids(state))
    boundary = normalize_scan_id(state.get("last_scan_id"))
    if boundary:
        index = next(
            (i for i, scan in enumerate(ordered) if scan.get("id") == boundary),
            None,
        )
        if index is not None:
            ordered = ordered[:index]
    return [scan for scan in ordered if scan.get("id") not in processed]


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
    try:
        failures = int(consecutive_failures)
        base_value = float(base)
        maximum_value = float(maximum)
        jitter = float(jitter_ratio)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if failures <= 0:
        return 0.0
    if not all(math.isfinite(v) for v in (base_value, maximum_value, jitter)):
        return 0.0

    base_value = max(0.0, base_value)
    maximum_value = max(0.0, maximum_value)
    jitter = min(1.0, max(0.0, jitter))
    exponent = min(base_value * (2 ** min(failures - 1, 64)), maximum_value)
    try:
        random_value = float(rng())
    except Exception:  # noqa: BLE001 - never let jitter break the loop
        random_value = 0.5
    random_value = min(1.0, max(0.0, random_value))
    factor = 1.0 + jitter * (2.0 * random_value - 1.0)
    return min(maximum_value, max(0.0, exponent * factor))


def describe_error(exc: BaseException) -> str:
    """Log-safe error label: type + HTTP status only, never bodies/tokens."""
    kind = safe_text(type(exc).__name__, 80) or "Exception"
    status_code: Any = None
    try:
        status_code = getattr(exc, "status_code", None)
    except Exception:  # noqa: BLE001 - hostile exception property
        status_code = None
    if status_code is None and isinstance(exc, httpx.HTTPStatusError):
        try:
            status_code = exc.response.status_code
        except Exception:  # noqa: BLE001
            status_code = None
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        return kind
    return f"{kind}(HTTP {status_code})"


def categorize_error(exc: BaseException) -> str:
    """Map an exception to a retry category without inspecting payloads."""
    if isinstance(exc, SyncConfigError):
        return "config"
    if isinstance(exc, RelayResponseError):
        return "transient"
    if isinstance(exc, (json.JSONDecodeError, httpx.DecodingError)):
        return "transient"
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            code = exc.response.status_code
        except Exception:  # noqa: BLE001
            return "error"
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


def _coerce_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return min(1_000_000, max(0, number))


def _coerce_status_state(value: Any) -> str:
    text = safe_text(value, 32)
    return text if text in VALID_STATUS_STATES else "idle"


def _coerce_error_category(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = safe_text(value, 32)
    return text if text in VALID_ERROR_CATEGORIES else None


@dataclass
class SyncStatus:
    """Small, log-safe snapshot of the background sync loop.

    ``state`` is one of: idle, syncing, offline, conflict, error.
    ``last_error_category`` uses the vocabulary from :func:`categorize_error`.
    Every field is validated in ``__post_init__`` so a malformed value can
    never reach a tray tooltip or Qt label.
    """

    state: str = "idle"
    last_sync_at: Optional[str] = None
    pending_in: int = 0
    pending_out: int = 0
    last_error_category: Optional[str] = None
    consecutive_failures: int = 0

    def __post_init__(self) -> None:
        self.state = _coerce_status_state(self.state)
        self.last_sync_at = _safe_iso(self.last_sync_at)
        self.pending_in = _coerce_count(self.pending_in)
        self.pending_out = _coerce_count(self.pending_out)
        self.last_error_category = _coerce_error_category(self.last_error_category)
        self.consecutive_failures = _coerce_count(self.consecutive_failures)

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


def push_catalog(context, client, version: Optional[int] = None,
                 base_revision: Optional[int] = None) -> Dict[str, Any]:
    """Push an ERP catalog snapshot with optimistic concurrency.

    The relay rejects a stale ``baseRevision`` with 409. On conflict we adopt
    the relay's current revision and retry once with the same snapshot, so an
    offline desktop cannot silently overwrite newer data.
    """
    from .catalog import build_catalog_payload

    state = load_state()
    if base_revision is None:
        base_revision = _nonneg_int(state.get("last_pushed_revision"), 0) or 0
    payload = build_catalog_payload(context, base_revision=base_revision)
    if version is not None:
        payload["version"] = version

    try:
        result = client.push_catalog(
            payload["version"], payload["products"],
            base_revision=payload["baseRevision"],
        )
    except Exception as exc:  # noqa: BLE001 - conflict payload is untrusted
        response = getattr(exc, "response", None)
        if response is None or getattr(response, "status_code", None) != 409:
            raise
        detail: Dict[str, Any] = {}
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                detail = parsed
        except Exception:  # noqa: BLE001 - malformed 409 must not crash the UI
            pass
        current = _nonneg_int(detail.get("currentRevision"), 0) or 0
        if current <= 0 or current == payload["baseRevision"]:
            raise
        payload["baseRevision"] = current
        result = client.push_catalog(
            payload["version"], payload["products"], base_revision=current,
        )

    state = load_state()
    state["last_pushed_version"] = payload["version"]
    state["last_pushed_revision"] = _nonneg_int(
        result.get("revision"), payload["baseRevision"],
    ) if isinstance(result, dict) else payload["baseRevision"]
    state["last_pushed_at"] = _now_iso()
    save_state(state)
    logger.info("Pushed catalog version %s (%s products, revision %s).",
                payload["version"], len(payload["products"]), state["last_pushed_revision"])
    return result


def pull_catalog(client, since_version: int = 0) -> Tuple[int, List[Dict[str, Any]]]:
    """Pull one catalog batch; 304 means the checkpoint is still current."""
    data = client.get_catalog(since_version)
    if data is None:  # HTTP 304
        return since_version, []
    if not isinstance(data, dict):
        raise RelayResponseError("Relay returned an unexpected catalog payload.")
    version = _nonneg_int(data.get("version", since_version), since_version)
    new_version = since_version if version is None else version
    products = data.get("products", [])
    if not isinstance(products, (list, tuple)):
        products = []
    state = load_state()
    state["last_pulled_version"] = new_version
    state["last_pulled_at"] = _now_iso()
    save_state(state)
    return new_version, list(products)


def diff_catalog(local_products: List[Dict[str, Any]], remote_products: List[Dict[str, Any]]) -> Dict[str, List]:
    """Simple SKU-keyed diff: added / removed / changed (price/stock)."""
    local = {
        p.get("sku"): p for p in (local_products or [])
        if isinstance(p, dict) and p.get("sku") is not None
    }
    remote = {
        p.get("sku"): p for p in (remote_products or [])
        if isinstance(p, dict) and p.get("sku") is not None
    }
    added = [p for sku, p in remote.items() if sku not in local]
    removed = [p for sku, p in local.items() if sku not in remote]
    changed = []
    for sku in local.keys() & remote.keys():
        if local[sku] != remote[sku]:
            changed.append({"sku": sku, "local": local[sku], "remote": remote[sku]})
    return {"added": added, "removed": removed, "changed": changed}
