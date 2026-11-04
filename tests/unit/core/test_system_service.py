"""System maintenance actions are privileged operations.

The low-level BackupManager/DiagnosticsManager remain context-free for the
startup and shutdown paths, so the authorization check lives in
SystemService and is verified here.
"""
import sqlite3

import pytest

from src.core.system_service import SystemService
from src.security.permissions import AccessDenied


def test_maintenance_operations_require_permission(unauthorized_context):
    with pytest.raises(AccessDenied):
        SystemService.list_backups(unauthorized_context)
    with pytest.raises(AccessDenied):
        SystemService.create_backup(unauthorized_context)
    with pytest.raises(AccessDenied):
        SystemService.restore_backup(unauthorized_context, "not-a-backup.zip")
    with pytest.raises(AccessDenied):
        SystemService.export_diagnostics(unauthorized_context)
    with pytest.raises(AccessDenied):
        SystemService.vacuum_database(unauthorized_context, "not-a-database.db")


def test_vacuum_requires_an_existing_database(admin_context, tmp_path):
    with pytest.raises(FileNotFoundError):
        SystemService.vacuum_database(
            admin_context, str(tmp_path / "missing.db")
        )


def test_vacuum_preserves_data(admin_context, tmp_path):
    db_path = tmp_path / "vacuum.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO t (value) VALUES ('kept')")
        conn.commit()
    finally:
        conn.close()

    SystemService.vacuum_database(admin_context, str(db_path))

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT value FROM t").fetchone()[0] == "kept"
    finally:
        conn.close()


def test_list_backups_is_read_only_and_allowed_for_admin(admin_context):
    assert isinstance(SystemService.list_backups(admin_context), list)
