import os
import shutil
import sqlite3
from typing import List, Dict, Tuple
from loguru import logger
from src.core.paths import DB_PATH, BACKUP_DIR, LOG_FILE_PATH
from src.core.version import APP_VERSION

class HealthStatus:
    OK = "OK"
    WARNING = "WARNING"
    FATAL = "FATAL"

class HealthCheckResult:
    def __init__(self, component: str, status: str, message: str):
        self.component = component
        self.status = status
        self.message = message

class HealthCheckEngine:
    """
    Validates the operational environment before the application boots.
    Implements Graceful Degradation:
    - FATAL: Core data safety is compromised. App must crash safely.
    - WARNING: Optional subsystems failed. App continues with degraded functionality.
    """
    
    MIN_DISK_SPACE_MB = 500
    CRITICAL_DISK_SPACE_MB = 50
    
    @staticmethod
    def run_all() -> List[HealthCheckResult]:
        logger.info("Starting System Health Check...")
        results = []
        
        # 1. Disk Space Verification
        results.append(HealthCheckEngine.check_disk_space())
        
        # 2. Backup Folder Permissions
        results.append(HealthCheckEngine.check_backup_folder())
        
        # 3. Database Integrity (if exists)
        if os.path.exists(DB_PATH):
            results.append(HealthCheckEngine.check_database_integrity())
        else:
            results.append(HealthCheckResult(
                "Database", HealthStatus.OK, "Database does not exist yet. Will be created."
            ))
            
        # 4. Logging Directory
        results.append(HealthCheckEngine.check_logging_access())

        # Log results
        for r in results:
            if r.status == HealthStatus.FATAL:
                logger.critical(f"HealthCheck [{r.component}]: {r.message}")
            elif r.status == HealthStatus.WARNING:
                logger.warning(f"HealthCheck [{r.component}]: {r.message}")
            else:
                logger.info(f"HealthCheck [{r.component}]: {r.message}")
                
        return results

    @staticmethod
    def check_disk_space() -> HealthCheckResult:
        try:
            # Check the drive where the DB resides (usually C:\ via %LOCALAPPDATA%)
            total, used, free = shutil.disk_usage(os.path.dirname(DB_PATH))
            free_mb = free / (1024 * 1024)
            
            if free_mb < HealthCheckEngine.CRITICAL_DISK_SPACE_MB:
                return HealthCheckResult(
                    "Disk Space", 
                    HealthStatus.FATAL, 
                    f"Critically low disk space: {free_mb:.1f} MB free. Minimum required: {HealthCheckEngine.CRITICAL_DISK_SPACE_MB} MB."
                )
            elif free_mb < HealthCheckEngine.MIN_DISK_SPACE_MB:
                return HealthCheckResult(
                    "Disk Space", 
                    HealthStatus.WARNING, 
                    f"Low disk space: {free_mb:.1f} MB free. Backups may fail soon."
                )
            return HealthCheckResult("Disk Space", HealthStatus.OK, f"Sufficient disk space ({free_mb:.1f} MB free).")
        except Exception as e:
            return HealthCheckResult("Disk Space", HealthStatus.WARNING, f"Could not determine disk space: {e}")

    @staticmethod
    def check_backup_folder() -> HealthCheckResult:
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            test_file = os.path.join(BACKUP_DIR, ".health_check_tmp")
            with open(test_file, 'w') as f:
                f.write("ok")
            os.remove(test_file)
            return HealthCheckResult("Backup Directory", HealthStatus.OK, "Writable.")
        except Exception as e:
            return HealthCheckResult(
                "Backup Directory", 
                HealthStatus.WARNING, 
                f"Backup directory is not writable. Automatic backups are disabled. ({e})"
            )

    @staticmethod
    def check_logging_access() -> HealthCheckResult:
        try:
            log_dir = os.path.dirname(LOG_FILE_PATH)
            os.makedirs(log_dir, exist_ok=True)
            test_file = os.path.join(log_dir, ".health_check_tmp")
            with open(test_file, 'w') as f:
                f.write("ok")
            os.remove(test_file)
            return HealthCheckResult("Logging", HealthStatus.OK, "Writable.")
        except Exception as e:
            return HealthCheckResult(
                "Logging", 
                HealthStatus.WARNING, 
                f"Logging directory is not writable. File logging may fail. ({e})"
            )

    @staticmethod
    def check_database_integrity() -> HealthCheckResult:
        try:
            import contextlib
            # We connect directly using sqlite3 to issue PRAGMAs safely outside SQLAlchemy
            with contextlib.closing(sqlite3.connect(DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchone()
            
            if result and result[0].lower() == "ok":
                return HealthCheckResult("Database Integrity", HealthStatus.OK, "PRAGMA integrity_check passed.")
            else:
                return HealthCheckResult(
                    "Database Integrity", 
                    HealthStatus.FATAL, 
                    f"Corruption detected. PRAGMA integrity_check returned: {result[0] if result else 'Unknown'}"
                )
        except Exception as e:
            return HealthCheckResult(
                "Database Integrity", 
                HealthStatus.FATAL, 
                f"Failed to execute integrity check: {e}"
            )
