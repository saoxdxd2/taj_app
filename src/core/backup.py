import os
import shutil
import zipfile
from datetime import datetime
from loguru import logger
from src.core.paths import DB_PATH, BACKUP_DIR

class BackupManager:
    @staticmethod
    def create_backup(prefix="manual") -> str:
        """
        Creates a zip backup of the current database.
        Prefix can be 'manual', 'shutdown', or 'pre_migration'.
        Returns the path to the backup file.
        """
        if not os.path.exists(DB_PATH):
            logger.warning("No database found to backup.")
            return ""

        try:
            # Disk space check before backup (requires at least 50MB free)
            from src.core.health_check import HealthCheckEngine, HealthStatus
            result = HealthCheckEngine.check_disk_space()
            if result.status == HealthStatus.FATAL:
                raise Exception(f"Insufficient disk space for backup: {result.message}")
                
            # Database Integrity check before backup (Prevent backing up corruption)
            integrity_result = HealthCheckEngine.check_database_integrity()
            if integrity_result.status == HealthStatus.FATAL:
                raise Exception(f"Database corruption detected. Backup aborted to prevent overwriting healthy backups. {integrity_result.message}")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"taj_froid_{prefix}_{timestamp}.zip"
            backup_path = os.path.join(BACKUP_DIR, backup_filename)

            import sqlite3
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_db_path = os.path.join(temp_dir, "taj_froid.db")
                
                # Safely copy using sqlite3 backup API to avoid torn database.
                # Explicitly close connections before the temp dir is zipped —
                # sqlite3's context manager commits but does NOT close on Windows.
                src = sqlite3.connect(str(DB_PATH))
                dst = sqlite3.connect(temp_db_path)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
                    src.close()
                        
                # Zip the safe snapshot
                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(temp_db_path, arcname="taj_froid.db")

            # Verify backup integrity
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                if zipf.testzip() is not None:
                    raise Exception("Backup archive is corrupted.")

            logger.info(f"Database backup created and verified: {backup_path}")
            
            # Retention Policy: Prune old backups
            BackupManager._apply_retention_policy()
            
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise

    @staticmethod
    def _apply_retention_policy(max_backups: int = 15):
        """
        Keeps only the most recent `max_backups` zip files.
        """
        backups = BackupManager.list_backups()
        if len(backups) > max_backups:
            for old_backup in backups[max_backups:]:
                try:
                    os.remove(old_backup)
                    logger.info(f"Retention policy: Deleted old backup {old_backup}")
                except OSError as e:
                    logger.warning(f"Retention policy: Failed to delete old backup {old_backup}: {e}")

    @staticmethod
    def restore_backup(backup_path: str):
        """
        Restores the database from a zip backup.
        This overwrites the current database.
        """
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        try:
            import tempfile
            import sqlite3
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # 1. Extract the backup to a temp location
                temp_db_path = os.path.join(temp_dir, "taj_froid.db")
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extract("taj_froid.db", path=temp_dir)
                    
                # 2. Create safety backup
                safety_backup = BackupManager.create_backup(prefix="pre_restore_safety")
                
                # 3. Dispose SQLAlchemy connections to release locks
                from src.database.session import engine
                engine.dispose()
                
                # 4. Safely overwrite DB_PATH using sqlite3 backup API
                with sqlite3.connect(temp_db_path) as src:
                    with sqlite3.connect(DB_PATH) as dst:
                        src.backup(dst)
                        
            logger.info(f"Database restored successfully from {backup_path}. Safety backup: {safety_backup}")
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            raise

    @staticmethod
    def list_backups() -> list:
        """
        Returns a sorted list of available backups (newest first).
        """
        if not os.path.exists(BACKUP_DIR):
            return []
            
        backups = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".zip") or f.endswith(".db")]
        backups.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return backups
