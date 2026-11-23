"""Qt-safe polling agent for the mobile relay.

Runs in a background QThread. Polls every 30s (with exponential backoff on
errors) and emits signals so the UI thread can react. Never blocks the UI.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QThread, Signal

from .client import RelayClient
from .inbox import process_scan, post_status

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30.0
MAX_BACKOFF = 300.0


class MobileAgent(QThread):
    new_scan_ready = Signal(object, object)   # (MobileScan row, InvoiceScan)
    scan_failed = Signal(str, str)            # (relay_id, message)
    status = Signal(str)

    def __init__(self, base_url: str, context, parent=None):
        super().__init__(parent)
        self._base_url = base_url
        self._context = context
        self._stop = False
        self._client = RelayClient(base_url)
        self._processed: set = set()

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        backoff = POLL_INTERVAL
        while not self._stop:
            try:
                scans = self._client.list_uploaded_scans(limit=10)
                backoff = POLL_INTERVAL
                for scan in scans:
                    if self._stop:
                        break
                    rid = scan.get("id")
                    if not rid or rid in self._processed:
                        continue
                    try:
                        row, invoice_scan = process_scan(self._context, self._client, scan)
                        self._processed.add(rid)
                        if invoice_scan is not None:
                            self.new_scan_ready.emit(row, invoice_scan)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Failed to process scan %s: %s", rid, exc)
                        self.scan_failed.emit(str(rid), str(exc))
                self.status.emit("ok")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Mobile agent poll failed: %s", exc)
                self.status.emit(f"error: {exc}")
                backoff = min(backoff * 2, MAX_BACKOFF)

            # Sleep in small increments so stop() is responsive.
            slept = 0.0
            while slept < backoff and not self._stop:
                time.sleep(min(1.0, backoff - slept))
                slept += 1.0