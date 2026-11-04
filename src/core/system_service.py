"""Authorized entry points for privileged maintenance operations.

Backup, restore, diagnostics and VACUUM are powerful enough that they must
not be callable by every signed-in user. The low-level managers in
``backup.py`` and ``diagnostics.py`` stay context-free because the startup
and shutdown paths use them before/after a user session exists; this thin
service is the boundary for operations initiated from the UI.
"""
import os
import sqlite3
from typing import Optional

from src.core.backup import BackupManager
from src.core.context import RequestContext
from src.core.diagnostics import DiagnosticsManager
from src.core.paths import DB_PATH
from src.security.permissions import AccessDenied, PermissionManager


class SystemService:
    """Context-aware facade for system maintenance actions."""

    PERMISSION = "Settings.System.Update"

    @staticmethod
    def _require(context: RequestContext) -> None:
        if context is None:
            raise AccessDenied(
                "Authentication is required for system maintenance."
            )
        PermissionManager.verify_permission(context, SystemService.PERMISSION)

    @staticmethod
    def list_backups(context: RequestContext) -> list:
        SystemService._require(context)
        return BackupManager.list_backups()

    @staticmethod
    def create_backup(context: RequestContext, prefix: str = "manual") -> str:
        SystemService._require(context)
        return BackupManager.create_backup(prefix=prefix)

    @staticmethod
    def restore_backup(context: RequestContext, backup_path: str):
        SystemService._require(context)
        return BackupManager.restore_backup(backup_path)

    @staticmethod
    def export_diagnostics(context: RequestContext) -> str:
        SystemService._require(context)
        return DiagnosticsManager.create_diagnostic_bundle()

    @staticmethod
    def vacuum_database(context: RequestContext,
                        db_path: Optional[str] = None) -> None:
        SystemService._require(context)
        target = db_path or DB_PATH
        if not os.path.exists(target):
            raise FileNotFoundError(f"Database not found: {target}")

        # VACUUM needs an exclusive lock. Close pooled SQLAlchemy
        # connections first, otherwise the operation fails with
        # "database is locked" while the UI still has a session open.
        from src.database.session import engine
        engine.dispose()

        conn = sqlite3.connect(target, timeout=10)
        try:
            conn.isolation_level = None
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("VACUUM")
        finally:
            conn.close()
