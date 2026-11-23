"""Inbox state for scans coming from the mobile relay.

One row per relay scan. Tracks the lifecycle on the desktop side:
fetched -> extracted -> needs_review -> imported | rejected | failed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey

from src.database.base import BaseModel


class MobileScanStatus(str):
    UPLOADED = "uploaded"
    FETCHED = "fetched"
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    IMPORTED = "imported"
    REJECTED = "rejected"
    FAILED = "failed"


# Use a plain str enum-like value stored as String to keep migrations simple.
from enum import Enum


class MobileScanState(str, Enum):
    UPLOADED = "uploaded"
    FETCHED = "fetched"
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    IMPORTED = "imported"
    REJECTED = "rejected"
    FAILED = "failed"


class MobileScan(BaseModel):
    __tablename__ = "mobile_scan"

    relay_scan_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=MobileScanState.UPLOADED.value, nullable=False, index=True)

    local_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    purchase_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase.id"), nullable=True)
    purchase_reference: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)