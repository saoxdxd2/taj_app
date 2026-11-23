"""Qt-safe polling agent for the mobile relay.

Runs in a background QThread. Polls every 30s (bounded exponential backoff
with jitter on transient errors) and emits signals so the UI thread can react.
Never blocks the UI. Credentials/config failures stop the loop instead of
retrying immediately. The plain-thread :class:`worker.TraySyncWorker` shares
the same :class:`worker.SyncEngine`.
"""
from __future__ import annotations

import logging
import time

from PySide6.QtCore import QThread, Signal

from .client import RelayClient
from .sync import SyncStatus
from .worker import BATCH_SIZE, POLL_INTERVAL, SyncEngine

logger = logging.getLogger(__name__)


class MobileAgent(QThread):
    new_scan_ready = Signal(object, object)   # (MobileScan row, InvoiceScan)
    scan_failed = Signal(str, str)            # (relay_id, message)
    status = Signal(str)                      # compact SyncStatus text

    def __init__(self, base_url: str, context, parent=None,
                 batch_size: int = BATCH_SIZE, poll_interval: float = POLL_INTERVAL):
        super().__init__(parent)
        self._context = context
        self._stop = False
        self._engine = SyncEngine(
            RelayClient(base_url), context,
            batch_size=batch_size, poll_interval=poll_interval,
        )
        # Kept for callers that peek at it; the durable checkpoint now lives
        # in sync.py's state file instead of this in-memory set.
        self._processed: set = set()

    def stop(self) -> None:
        self._stop = True

    def get_status(self) -> SyncStatus:
        """Minimal accessor for status surfaces (tray/UI)."""
        return self._engine.get_status()

    def run(self) -> None:
        delay = 0.0
        while not self._stop:
            if delay and self._sleep(delay):
                break
            delay = self._engine.run_once(
                on_scan=lambda row, invoice_scan: self.new_scan_ready.emit(row, invoice_scan),
                on_scan_failed=lambda rid, message: self.scan_failed.emit(rid, message),
                on_status=lambda st: self.status.emit(st.compact()),
                should_stop=lambda: self._stop,
            )
            if delay is None:
                break

    def _sleep(self, seconds: float) -> bool:
        """Sleep in small increments so stop() stays responsive."""
        slept = 0.0
        while slept < seconds and not self._stop:
            step = min(1.0, seconds - slept)
            time.sleep(step)
            slept += step
        return self._stop
