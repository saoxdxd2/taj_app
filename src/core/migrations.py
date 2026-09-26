"""Database schema migrations with recoverable failure handling.

Extracted from main.py so the migration step can be tested, retried, and
recovered from without terminating the interpreter.

A failed Alembic upgrade is never safe to "just retry" blindly: the schema
may be half-applied. That is why a backup is taken first and its path is
carried in MigrationResult, so the UI can offer to restore it.
"""
import os
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from src.core.paths import DB_PATH


@dataclass
class MigrationResult:
    """
    Outcome of a migration attempt.

    success      - True when the database is at head.
    error        - The failure message, when success is False.
    backup_path  - Pre-migration backup, kept so a recovery dialog can offer
                   to restore it. None when no backup was taken.
    """
    success: bool
    error: Optional[str] = None
    backup_path: Optional[str] = None


def _alembic_config():
    """Builds the Alembic config pointed at the live database."""
    from alembic.config import Config

    project_root = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    ))
    alembic_ini_path = os.path.join(project_root, "alembic.ini")
    cfg = Config(alembic_ini_path)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")
    return cfg


def create_pre_migration_backup() -> Optional[str]:
    """
    Takes a backup before migrating. Returns its path, or None if the
    database does not exist yet (a fresh install has nothing to protect).
    """
    if not os.path.exists(DB_PATH):
        return None
    from src.core.backup import BackupManager
    return BackupManager.create_backup(prefix="pre_migration")


def apply_migrations() -> MigrationResult:
    """
    Upgrades the database to head.

    Never raises and never calls sys.exit: a failure is returned as data so
    the caller can offer a recovery path instead of dying.
    """
    try:
        backup_path = create_pre_migration_backup()
    except Exception as exc:
        # Refuse to migrate without a safety net.
        message = f"Pre-migration backup failed: {exc}"
        logger.error(message)
        return MigrationResult(success=False, error=message, backup_path=None)

    try:
        logger.info("Executing database migrations...")
        from alembic import command
        command.upgrade(_alembic_config(), "head")
        logger.info("Database migrations completed successfully.")
        return MigrationResult(success=True, backup_path=backup_path)
    except Exception as exc:
        message = str(exc)
        logger.error(f"Migration failed: {message}")
        return MigrationResult(
            success=False, error=message, backup_path=backup_path
        )
