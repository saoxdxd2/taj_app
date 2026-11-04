import os
import shutil
import zipfile
from datetime import datetime
from typing import Optional
from loguru import logger
from src.core.paths import DB_PATH, BACKUP_DIR, TEMP_DIR


def _configured_int(key: str, fallback: int) -> int:
    """
    Reads a numeric system setting, falling back to a literal when the
    database is unavailable (e.g. before the first migration, or while the
    database is locked or corrupt).

    Backups must keep working even when the settings table cannot be read,
    so a failure here is logged and ignored rather than raised.
    """
    try:
        from src.modules.settings.services import SettingsService
        from src.core.context import RequestContext
        from src.database.session import SessionLocal

        context = RequestContext(
            user_id="0", username="system", role="System", permissions={"Everything"}
        )
        session = SessionLocal()
        try:
            return SettingsService.get_int(context=context, session=session, key=key)
        finally:
            session.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            f"Could not read setting '{key}' ({exc}); using default {fallback}."
        )
        return fallback


class BackupManager:
    @staticmethod
    def create_backup(prefix="manual", require_integrity: bool = True) -> str:
        """
        Creates a zip backup of the current database.
        Prefix can be 'manual', 'shutdown', or 'pre_migration'.

        `require_integrity` is true for ordinary backups: never overwrite a
        healthy backup with a corrupt source. A pre-restore safety copy sets
        it to false, because the live database may be the reason the restore
        was requested in the first place.

        Returns the path to the backup file.
        """
        if not os.path.exists(DB_PATH):
            logger.warning("No database found to backup.")
            return ""

        backup_path = None
        try:
            # Disk space check before backup (requires at least 50MB free)
            from src.core.health_check import HealthCheckEngine, HealthStatus
            result = HealthCheckEngine.check_disk_space()
            if result.status == HealthStatus.FATAL:
                raise Exception(f"Insufficient disk space for backup: {result.message}")

            if require_integrity:
                # Prevent backing up corruption over healthy backups.
                integrity_result = HealthCheckEngine.check_database_integrity()
                if integrity_result.status == HealthStatus.FATAL:
                    raise Exception(
                        "Database corruption detected. Backup aborted to "
                        "prevent overwriting healthy backups. "
                        f"{integrity_result.message}"
                    )

            # Microseconds avoid two backups created in the same second
            # overwriting each other (and a later cleanup deleting the
            # wrong archive).
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_filename = f"taj_froid_{prefix}_{timestamp}.zip"
            backup_path = os.path.join(BACKUP_DIR, backup_filename)

            import sqlite3
            import tempfile
            # Keep scratch files inside the application data tree. The
            # shared Windows %TEMP% folder can be ACL-locked on shop PCs,
            # which would make every backup fail before it starts.
            with tempfile.TemporaryDirectory(dir=str(TEMP_DIR)) as temp_dir:
                temp_db_path = os.path.join(temp_dir, "taj_froid.db")
                
                # Safely copy using sqlite3 backup API to avoid torn database.
                # Explicitly close connections before the temp dir is zipped —
                # sqlite3's context manager commits but does NOT close on Windows.
                src = sqlite3.connect(str(DB_PATH))
                dst = None
                try:
                    dst = sqlite3.connect(temp_db_path)
                    src.backup(dst)
                finally:
                    try:
                        if dst is not None:
                            dst.close()
                    finally:
                        src.close()
                        
                # Zip the safe snapshot
                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(temp_db_path, arcname="taj_froid.db")

            # Verify backup integrity
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                if zipf.testzip() is not None:
                    raise Exception("Backup archive is corrupted.")

            logger.info(f"Database backup created and verified: {backup_path}")
            
            # Retention is housekeeping, not part of the backup contract.
            # A permission error or a file removed by another process must
            # not turn a successful backup into a reported failure.
            try:
                BackupManager._apply_retention_policy()
            except Exception as retention_error:
                logger.warning(
                    f"Backup retention policy failed (backup is still valid): "
                    f"{retention_error}"
                )
            
            return backup_path
        except Exception as e:
            # Do not leave a partial archive behind: the next restore or
            # retention pass must never pick up a corrupt backup.
            if backup_path and os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except OSError as cleanup_error:
                    logger.warning(
                        f"Could not remove incomplete backup {backup_path}: "
                        f"{cleanup_error}"
                    )
            logger.error(f"Failed to create backup: {e}")
            raise

    @staticmethod
    def _apply_retention_policy(max_backups: Optional[int] = None) -> None:
        """
        Keeps only the most recent `max_backups` zip files.

        When no explicit count is given, the value is read from the
        `backup.retention.count` system setting (default 15).
        """
        if max_backups is None:
            from src.modules.settings.models import SettingKey
            max_backups = _configured_int(SettingKey.BACKUP_RETENTION_COUNT, 15)
        # A corrupted setting must never delete every backup on disk.
        max_backups = max(1, int(max_backups))

        backups = BackupManager.list_backups()
        if len(backups) > max_backups:
            for old_backup in backups[max_backups:]:
                try:
                    os.remove(old_backup)
                    logger.info(f"Retention policy: Deleted old backup {old_backup}")
                except OSError as e:
                    logger.warning(f"Retention policy: Failed to delete old backup {old_backup}: {e}")

    @staticmethod
    def _is_valid_backup_path(backup_path: str) -> bool:
        """
        SECURITY: a restore overwrites the live database, so the source
        file is constrained before it is opened.

        Only a real .zip file is accepted, and it must not be a symlink or
        point outside the backup directory unless the caller explicitly
        imported it. The import path is the reason a hard "must be inside
        BACKUP_DIR" check is not enforced here: the UI offers "Restore
        from File...", so legitimate backups live elsewhere on disk. What
        is refused is anything that is not a regular zip file, which is
        what an arbitrary-path attack would need.
        """
        if not backup_path:
            return False
        try:
            resolved = os.path.realpath(backup_path)
        except (OSError, ValueError):
            return False

        if not os.path.isfile(resolved):
            return False
        # Refuse symlinks: a link could point at something that is not a
        # backup at all, and the name would look legitimate.
        if os.path.islink(backup_path):
            return False
        if not resolved.lower().endswith(".zip"):
            return False
        return zipfile.is_zipfile(resolved)

    @staticmethod
    def _validate_restore_archive(backup_path: str) -> None:
        """Checks the archive shape before extracting anything.

        A restore accepts a user-selected zip, so the archive must contain
        the expected database member. This rejects a zip that only happens
        to have a .zip extension, and only the known member name is ever
        extracted.
        """
        with zipfile.ZipFile(backup_path, "r") as archive:
            try:
                member = archive.getinfo("taj_froid.db")
            except KeyError as exc:
                raise ValueError(
                    "Refusing to restore: the archive does not contain "
                    "taj_froid.db."
                ) from exc
            if member.is_dir():
                raise ValueError(
                    "Refusing to restore: taj_froid.db is a directory in "
                    "the archive."
                )

    @staticmethod
    def _validate_sqlite_database(database_path: str) -> None:
        """Verifies that a restored file really is a healthy SQLite DB.

        The UI accepts an externally supplied backup file. Checking only
        the zip extension is not enough: a valid zip can still contain
        arbitrary bytes, which would replace the live database with an
        unreadable file. The header and integrity check happen before the
        live database is touched.
        """
        import sqlite3

        with open(database_path, "rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                raise ValueError(
                    "Refusing to restore: the archive does not contain a "
                    "SQLite database."
                )

        conn = sqlite3.connect(database_path)
        try:
            result = conn.execute("PRAGMA integrity_check;").fetchone()
        except sqlite3.DatabaseError as exc:
            raise ValueError(
                "Refusing to restore: the backup database is unreadable."
            ) from exc
        finally:
            conn.close()
        if not result or str(result[0]).lower() != "ok":
            raise ValueError(
                "Refusing to restore: the backup database failed its "
                "integrity check."
            )

    @staticmethod
    def restore_backup(backup_path: str):
        """
        Restores the database from a zip backup.
        This overwrites the current database.
        """
        if not BackupManager._is_valid_backup_path(backup_path):
            raise ValueError(
                "Refusing to restore: the file must be an existing, "
                "non-symlink .zip backup."
            )
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        try:
            import tempfile
            import sqlite3

            BackupManager._validate_restore_archive(backup_path)

            with tempfile.TemporaryDirectory(dir=str(TEMP_DIR)) as temp_dir:
                # 1. Extract the backup to a temp location
                temp_db_path = os.path.join(temp_dir, "taj_froid.db")
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extract("taj_froid.db", path=temp_dir)

                # 2. Validate the extracted database before touching the
                #    live one.
                BackupManager._validate_sqlite_database(temp_db_path)

                # 3. Best-effort safety copy of the current state. The live
                #    database may be corrupt (which is often why a restore is
                #    requested), so this copy must not run the ordinary
                #    integrity gate. A failure here is logged but does not
                #    block recovery from the already-validated source.
                try:
                    safety_backup = BackupManager.create_backup(
                        prefix="pre_restore_safety", require_integrity=False
                    )
                except Exception as safety_error:
                    safety_backup = ""
                    logger.warning(
                        "Pre-restore safety backup failed; continuing with "
                        f"the validated restore source: {safety_error}"
                    )

                # 4. Dispose SQLAlchemy connections to release locks
                from src.database.session import engine
                engine.dispose()

                # 5. Safely overwrite DB_PATH using sqlite3 backup API.
                # The sqlite3 context manager commits but does not close on
                # Windows, so both connections must be closed explicitly.
                # Otherwise the live database (and the temp snapshot) stay
                # locked after a restore.
                src = sqlite3.connect(temp_db_path)
                dst = None
                try:
                    dst = sqlite3.connect(DB_PATH)
                    src.backup(dst)
                finally:
                    try:
                        if dst is not None:
                            dst.close()
                    finally:
                        src.close()

            logger.info(f"Database restored successfully from {backup_path}. Safety backup: {safety_backup}")
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            raise

    @staticmethod
    def list_backups() -> list:
        """
        Returns the restorable backups, newest first.

        Only .zip files are listed: restore_backup intentionally refuses a
        bare .db file, so showing one in the UI would only produce a failed
        restore. A file that disappears between listdir() and stat() is
        skipped rather than failing the whole listing.
        """
        if not os.path.isdir(BACKUP_DIR):
            return []

        try:
            filenames = os.listdir(BACKUP_DIR)
        except OSError:
            return []

        entries = []
        for filename in filenames:
            if not filename.lower().endswith(".zip"):
                continue
            path = os.path.join(BACKUP_DIR, filename)
            try:
                entries.append((os.path.getmtime(path), path))
            except OSError:
                continue
        entries.sort(key=lambda item: item[0], reverse=True)
        return [path for _, path in entries]
