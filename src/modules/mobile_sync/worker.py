"""Plain-thread sync loop shared by the tray service and the Qt agent.

The loop uses the durable checkpoint from :mod:`sync`, processes relay scans
in batches (the client already supports a ``limit``) and keeps a small
thread-safe :class:`~sync.SyncStatus` snapshot of every cycle.

A batch boundary is only committed when *every* scan in the batch succeeded.
A single failed scan (even the oldest one) leaves the previous boundary in
place, so restarting retries it instead of silently skipping it.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .client import RelayClient
from .sync import (
    MAX_BACKOFF,
    TERMINAL_CATEGORIES,
    SyncStatus,
    categorize_error,
    compute_backoff,
    describe_error,
    mark_scan_processed,
    normalize_scan_id,
    pending_scan_ids,
    set_scan_boundary,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30.0
BATCH_SIZE = 25


def _pending_out_count() -> int:
    """Local scans still awaiting status/review (best effort, never fatal)."""
    try:
        from src.database.session import SessionLocal
        from .models import MobileScan, MobileScanState
        with SessionLocal() as session:
            return session.query(MobileScan).filter(
                MobileScan.status.in_([
                    MobileScanState.FETCHED.value,
                    MobileScanState.EXTRACTED.value,
                    MobileScanState.NEEDS_REVIEW.value,
                ])
            ).count()
    except Exception as exc:  # noqa: BLE001 - status must never break the loop
        logger.debug("Could not count pending outbound scans: %s", describe_error(exc))
        return 0


class SyncEngine:
    """One cycle of the sync loop, independent of any UI toolkit."""

    def __init__(self, client: RelayClient, context, batch_size: int = BATCH_SIZE,
                 poll_interval: float = POLL_INTERVAL, max_backoff: float = MAX_BACKOFF):
        self.client = client
        self.context = context
        self.batch_size = max(1, int(batch_size))
        self.poll_interval = poll_interval
        self.max_backoff = max_backoff
        self.status = SyncStatus()
        self._lock = threading.RLock()

    def get_status(self) -> SyncStatus:
        with self._lock:
            return self.status.snapshot()

    def _patch_status(self, **fields: Any) -> SyncStatus:
        """Apply validated fields atomically; bad values never reach the UI."""
        with self._lock:
            data = self.status.to_dict()
            data.update(fields)
            self.status = SyncStatus(**data)
            return self.status.snapshot()

    def run_once(
        self,
        on_scan: Optional[Callable[[Any, Any], None]] = None,
        on_scan_failed: Optional[Callable[[str, str], None]] = None,
        on_status: Optional[Callable[[SyncStatus], None]] = None,
        should_stop: Callable[[], bool] = lambda: False,
    ) -> Optional[float]:
        """Process one batch. Returns delay to next cycle, or None to stop."""
        self._patch_status(state="syncing")
        try:
            scans = self.client.list_uploaded_scans(limit=self.batch_size) or []
            pending = pending_scan_ids(scans, limit=self.batch_size)
            self._patch_status(
                pending_in=len(pending),
                pending_out=_pending_out_count(),
                state="syncing" if pending else "idle",
            )

            successful_ids = []
            had_scan_failure = False
            for scan in pending:
                if should_stop():
                    return None
                relay_id = normalize_scan_id(scan.get("id")) if isinstance(scan, dict) else None
                try:
                    if relay_id is None:
                        had_scan_failure = True
                        logger.warning("Skipping a malformed relay scan entry.")
                        continue
                    from .inbox import process_scan
                    row, invoice_scan = process_scan(self.context, self.client, scan)
                    # Record the scan, but never move the resume boundary yet:
                    # a later (older) scan in this batch may still fail.
                    mark_scan_processed(relay_id, advance_boundary=False)
                    successful_ids.append(relay_id)
                    with self._lock:
                        self.status.pending_in = max(0, self.status.pending_in - 1)
                    if on_scan is not None and invoice_scan is not None:
                        on_scan(row, invoice_scan)
                except Exception as exc:  # noqa: BLE001 - one bad scan must not kill the loop
                    had_scan_failure = True
                    category = categorize_error(exc)
                    label = relay_id or "<invalid>"
                    logger.warning("Scan %s failed (category=%s): %s",
                                   label, category, describe_error(exc))
                    if category in TERMINAL_CATEGORIES:
                        # Auth/config problems are not scan-specific: stop the loop.
                        with self._lock:
                            failures = self.status.consecutive_failures + 1
                        self._patch_status(
                            state="conflict" if category == "conflict" else "error",
                            last_error_category=category,
                            consecutive_failures=failures,
                        )
                        if on_status is not None:
                            on_status(self.get_status())
                        return None
                    if on_scan_failed is not None:
                        on_scan_failed(label, describe_error(exc))

            if not had_scan_failure and successful_ids:
                # The relay lists newest first: the last success is the oldest
                # processed scan, i.e. the safe resume boundary.
                set_scan_boundary(successful_ids[-1])

            snapshot = self._patch_status(
                state="syncing" if pending else "idle",
                pending_out=_pending_out_count(),
                last_sync_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                consecutive_failures=0,
                last_error_category=None,
            )
            if on_status is not None:
                on_status(snapshot)
            return self.poll_interval
        except Exception as exc:  # noqa: BLE001 - relay failure
            category = categorize_error(exc)
            with self._lock:
                failures = self.status.consecutive_failures + 1
            if category in TERMINAL_CATEGORIES:
                snapshot = self._patch_status(
                    state="conflict" if category == "conflict" else "error",
                    last_error_category=category,
                    consecutive_failures=failures,
                )
                logger.warning("Mobile sync stopped (%s): %s", category, describe_error(exc))
                delay = None  # never loop on auth/config/conflict
            else:
                snapshot = self._patch_status(
                    state="offline",
                    last_error_category=category,
                    consecutive_failures=failures,
                )
                delay = compute_backoff(failures, maximum=self.max_backoff)
                logger.warning(
                    "Mobile sync poll failed (category=%s, failures=%d, retry in %.1fs): %s",
                    category, failures, delay, describe_error(exc),
                )
            if on_status is not None:
                on_status(snapshot)
            return delay


class TraySyncWorker(threading.Thread):
    """Daemon thread used by ``mobile_tray.py``; no Qt event loop required."""

    def __init__(self, base_url: str, context, token: Optional[str] = None,
                 batch_size: int = BATCH_SIZE, poll_interval: float = POLL_INTERVAL):
        super().__init__(name="mobile-sync", daemon=True)
        self._stop_event = threading.Event()
        self.engine = SyncEngine(
            RelayClient(base_url, token=token), context,
            batch_size=batch_size, poll_interval=poll_interval,
        )

    def stop(self) -> None:
        self._stop_event.set()

    def wait(self, timeout_ms: Optional[int] = None) -> None:
        self.join(None if timeout_ms is None else max(0, timeout_ms) / 1000.0)

    def get_status(self) -> SyncStatus:
        return self.engine.get_status()

    def run(self) -> None:
        delay = 0.0
        while not self._stop_event.is_set():
            if delay and self._stop_event.wait(delay):
                break
            delay = self.engine.run_once(should_stop=self._stop_event.is_set)
            if delay is None:
                break
