"""Inbox: download, decrypt and OCR a scan from the relay.

The desktop is the only place that OCRs. This module turns a relay scan
into an InvoiceScan ready for the existing review dialog.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from src.core.context import RequestContext
from src.core.paths import TEMP_DIR
from src.modules.mobile_sync.crypto import (
    decrypt_sealed_box, sha256_bytes, verify_jpeg_magic,
)
from src.modules.mobile_sync.models import MobileScan, MobileScanState
from src.modules.mobile_sync.sync import describe_error, normalize_scan_id, safe_text

logger = logging.getLogger(__name__)

MAX_BYTES = 3 * 1024 * 1024


def _inbox_dir() -> Path:
    d = TEMP_DIR / "mobile_inbox"
    d.mkdir(parents=True, exist_ok=True)
    return d


def process_scan(context: RequestContext, client, relay_scan: dict) -> Tuple[MobileScan, Optional[object]]:
    """Download + decrypt + OCR one scan. Returns (mobile_scan_row, invoice_scan).

    On any failure the row is marked FAILED and the exception is re-raised
    so the caller can report it. Tokens/file contents are never logged.
    """
    from src.database.session import SessionLocal
    from src.modules.purchasing.invoice_import import InvoiceImportService

    relay_id = normalize_scan_id(
        relay_scan.get("id") if isinstance(relay_scan, dict) else None
    )
    if relay_id is None:
        # Invalid IDs are dropped before this point in normal operation.
        raise ValueError("Invalid relay scan ID.")
    client_id = safe_text(
        relay_scan.get("clientId") or relay_scan.get("client_id"), 36
    )
    with SessionLocal() as session:
        row = session.query(MobileScan).filter(MobileScan.relay_scan_id == relay_id).first()
        if row is None:
            row = MobileScan(
                relay_scan_id=relay_id,
                client_id=client_id or None,
                captured_at=_parse_dt(relay_scan.get("capturedAt") or relay_scan.get("captured_at")),
                status=MobileScanState.UPLOADED.value,
            )
            session.add(row)
            session.commit()
            session.refresh(row)

    # Download ciphertext.
    try:
        ciphertext = client.download_scan_file(relay_id)
    except Exception as exc:  # noqa: BLE001
        post_status(client, relay_id, "failed", message=f"download failed: {describe_error(exc)}")
        _update_row(relay_id, status=MobileScanState.FAILED.value,
                    message=f"download failed: {describe_error(exc)}")
        raise

    if len(ciphertext) > MAX_BYTES:
        _set_status(relay_id, MobileScanState.FAILED.value, message="payload too large")
        raise ValueError("Decrypted payload exceeds the size limit.")

    # Decrypt.
    try:
        plaintext = decrypt_sealed_box(ciphertext)
    except Exception as exc:  # noqa: BLE001
        post_status(client, relay_id, "failed", message="decryption failed")
        _update_row(relay_id, status=MobileScanState.FAILED.value, message="decryption failed")
        raise

    if not verify_jpeg_magic(plaintext):
        post_status(client, relay_id, "failed", message="not a JPEG")
        _update_row(relay_id, status=MobileScanState.FAILED.value, message="not a JPEG")
        raise ValueError("Decrypted payload is not a JPEG image.")

    if len(plaintext) > MAX_BYTES:
        post_status(client, relay_id, "failed", message="image too large")
        _update_row(relay_id, status=MobileScanState.FAILED.value, message="image too large")
        raise ValueError("Decrypted image exceeds the size limit.")

    file_hash = sha256_bytes(plaintext)
    # Dedupe using existing source_file_hash.
    from src.modules.purchasing.models import Purchase
    from src.database.session import SessionLocal as SL
    with SL() as session:
        dup = session.query(Purchase).filter(Purchase.source_file_hash == file_hash).first()
        if dup is not None:
            post_status(client, relay_id, "imported", purchase_reference=dup.reference,
                        message="duplicate of an existing import")
            path = _inbox_dir() / f"{file_hash}.jpg"
            path.write_bytes(plaintext)
            _update_row(relay_id, local_file_path=str(path), file_hash=file_hash,
                        status=MobileScanState.IMPORTED.value,
                        purchase_reference=dup.reference)
            return None, None  # type: ignore

    # Persist the decrypted JPEG for OCR + review.
    path = _inbox_dir() / f"{relay_id}.jpg"
    path.write_bytes(plaintext)

    _update_row(relay_id, local_file_path=str(path), file_hash=file_hash,
                status=MobileScanState.FETCHED.value)
    post_status(client, relay_id, "fetched")

    # OCR via the existing pipeline.
    try:
        invoice_scan = InvoiceImportService.scan(context, path)
    except Exception as exc:  # noqa: BLE001
        post_status(client, relay_id, "failed", message=f"ocr failed: {describe_error(exc)}")
        _update_row(relay_id, status=MobileScanState.FAILED.value,
                    message=f"ocr failed: {describe_error(exc)}")
        raise

    _update_row(relay_id, status=MobileScanState.NEEDS_REVIEW.value)
    post_status(client, relay_id, "needs_review")
    return _get_row(relay_id), invoice_scan


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(tzinfo=None)
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, OverflowError, OSError):
        return None


def post_status(client, relay_id: str, status: str,
                purchase_reference: Optional[str] = None,
                message: Optional[str] = None) -> None:
    """Best-effort status push to the relay. Never raises or logs bodies."""
    safe_id = normalize_scan_id(relay_id)
    if safe_id is None:
        return
    try:
        client.post_scan_status(safe_id, status,
                                purchase_reference=safe_text(purchase_reference, 50),
                                message=safe_text(message, 500))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not push status %s for %s: %s",
                       safe_text(status, 20), safe_id, describe_error(exc))


def _update_row(relay_id: str, **fields) -> None:
    from src.database.session import SessionLocal
    with SessionLocal() as session:
        row = session.query(MobileScan).filter(MobileScan.relay_scan_id == relay_id).first()
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()


def _get_row(relay_id: str) -> Optional[MobileScan]:
    from src.database.session import SessionLocal
    with SessionLocal() as session:
        row = session.query(MobileScan).filter(MobileScan.relay_scan_id == relay_id).first()
        if row is None:
            return None
        session.expunge(row)
        return row