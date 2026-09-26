"""
Tests for migration failure handling.

The key property: apply_migrations never raises and never exits the
interpreter. A failure is returned as data, with the pre-migration backup
path attached so the UI can offer to restore it.

These are pure unit tests: the Alembic command and the backup step are
both stubbed, so running the suite must never touch the real database.
"""
import pytest

from src.core.migrations import (
    MigrationResult, apply_migrations, create_pre_migration_backup,
)


# --- Success ------------------------------------------------------------

def test_apply_migrations_reports_success(monkeypatch):
    monkeypatch.setattr(
        "src.core.migrations.create_pre_migration_backup", lambda: "/tmp/b.zip"
    )
    # Stub the real upgrade so this test never runs against the live DB.
    monkeypatch.setattr("alembic.command.upgrade", lambda cfg, rev: None)

    result = apply_migrations()
    assert result.success is True
    assert result.error is None
    assert result.backup_path == "/tmp/b.zip"


# --- Failure ------------------------------------------------------------

def test_failure_is_returned_not_raised(monkeypatch):
    """A broken migration must not crash startup; it must return a result."""
    monkeypatch.setattr(
        "src.core.migrations.create_pre_migration_backup", lambda: "/tmp/b.zip"
    )
    monkeypatch.setattr(
        "src.core.migrations._alembic_config",
        lambda: (_ for _ in ()).throw(RuntimeError("schema is broken")),
    )
    result = apply_migrations()
    assert result.success is False
    assert "schema is broken" in result.error
    # The backup survives so the UI can offer a restore.
    assert result.backup_path == "/tmp/b.zip"


def test_backup_failure_refuses_to_migrate(monkeypatch):
    """
    Never migrate without a safety net: if the backup cannot be taken,
    the migration must not run.
    """
    def boom():
        raise RuntimeError("disk full")

    monkeypatch.setattr("src.core.migrations.create_pre_migration_backup", boom)

    def fail_if_called():
        raise AssertionError("migration must not run without a backup")

    monkeypatch.setattr("src.core.migrations._alembic_config", fail_if_called)

    result = apply_migrations()
    assert result.success is False
    assert "Pre-migration backup failed" in result.error
    assert result.backup_path is None


def test_backup_is_skipped_when_database_absent(monkeypatch):
    """A fresh install has no database, so there is nothing to back up."""
    monkeypatch.setattr("src.core.migrations.DB_PATH", "/nonexistent/taj_froid.db")
    assert create_pre_migration_backup() is None


# --- Result contract ----------------------------------------------------

def test_migration_result_defaults_are_safe():
    """A bare failure result must still be usable by the UI."""
    result = MigrationResult(success=False, error="boom")
    assert result.backup_path is None
    assert result.success is False
