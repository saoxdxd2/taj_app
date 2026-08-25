"""
Infrastructure health monitoring.

Runs lightweight checks against the live system and reports them as
structured results so the UI can surface problems before they hurt:
- Database integrity (PRAGMA integrity_check / foreign_key_check)
- Disk space on the data volume
- Backup freshness
"""
import shutil
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from typing import List

from loguru import logger


class HealthStatus(str, Enum):
    OK = "OK"
    WARN = "WARN"
    CRIT = "CRIT"


class HealthMonitor:
    """Static collection of infrastructure health checks."""

    # Thresholds
    MIN_FREE_DISK_BYTES = 1 * 1024 * 1024 * 1024      # 1 GB
    BACKUP_MAX_AGE_DAYS = 7

    @staticmethod
    def check_database(db_path) -> dict:
        """Integrity + foreign key consistency of the SQLite database."""
        result = {"name": "Database integrity", "status": HealthStatus.OK.value, "detail": ""}
        try:
            import os
            if not os.path.exists(str(db_path)):
                result["status"] = HealthStatus.CRIT.value
                result["detail"] = f"Database file not found: {db_path}"
                return result
            conn = sqlite3.connect(str(db_path))
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            finally:
                conn.close()

            if integrity != "ok":
                result["status"] = HealthStatus.CRIT.value
                result["detail"] = f"integrity_check reported: {integrity}"
            elif fk_violations:
                result["status"] = HealthStatus.CRIT.value
                result["detail"] = f"{len(fk_violations)} foreign key violation(s)"
            else:
                result["detail"] = "integrity ok, no FK violations"
        except Exception as e:
            result["status"] = HealthStatus.CRIT.value
            result["detail"] = f"Check failed: {e}"
            logger.error(f"Health check 'database' failed: {e}")
        return result

    @staticmethod
    def check_disk_space(path) -> dict:
        """Free space on the volume hosting the application data."""
        result = {"name": "Disk space", "status": HealthStatus.OK.value, "detail": ""}
        try:
            usage = shutil.disk_usage(str(path))
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            result["detail"] = f"{free_gb:.1f} GB free of {total_gb:.1f} GB"
            if usage.free < HealthMonitor.MIN_FREE_DISK_BYTES:
                result["status"] = HealthStatus.CRIT.value
                result["detail"] += " - CRITICALLY LOW"
            elif usage.free < HealthMonitor.MIN_FREE_DISK_BYTES * 5:
                result["status"] = HealthStatus.WARN.value
                result["detail"] += " - running low"
        except Exception as e:
            result["status"] = HealthStatus.CRIT.value
            result["detail"] = f"Check failed: {e}"
            logger.error(f"Health check 'disk' failed: {e}")
        return result

    @staticmethod
    def check_backups(backup_dir) -> dict:
        """Is there a recent backup? Warns when none within BACKUP_MAX_AGE_DAYS."""
        result = {"name": "Backup freshness", "status": HealthStatus.OK.value, "detail": ""}
        try:
            from pathlib import Path
            zips = sorted(
                Path(backup_dir).glob("*.zip"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not zips:
                result["status"] = HealthStatus.WARN.value
                result["detail"] = "No backups found yet"
                return result

            newest_mtime = datetime.fromtimestamp(zips[0].stat().st_mtime, tz=timezone.utc)
            age_days = (datetime.now(timezone.utc) - newest_mtime).total_seconds() / 86400
            age_str = f"latest backup {age_days:.1f} day(s) old ({zips[0].name})"
            if age_days > HealthMonitor.BACKUP_MAX_AGE_DAYS:
                result["status"] = HealthStatus.WARN.value
                result["detail"] = age_str + f" - older than {HealthMonitor.BACKUP_MAX_AGE_DAYS} days"
            else:
                result["detail"] = age_str
        except Exception as e:
            result["status"] = HealthStatus.WARN.value
            result["detail"] = f"Check failed: {e}"
            logger.error(f"Health check 'backups' failed: {e}")
        return result

    @staticmethod
    def run_all_checks(db_path=None, backup_dir=None, disk_path=None) -> List[dict]:
        """Run every applicable check and return the list of results."""
        from src.core.paths import DB_PATH, BACKUP_DIR, BASE_DATA_DIR

        results = []
        results.append(HealthMonitor.check_database(db_path or DB_PATH))
        results.append(HealthMonitor.check_disk_space(disk_path or BASE_DATA_DIR))
        results.append(HealthMonitor.check_backups(backup_dir or BACKUP_DIR))
        return results

    @staticmethod
    def overall_status(results: List[dict]) -> str:
        """Worst status across all checks."""
        order = {HealthStatus.OK.value: 0, HealthStatus.WARN.value: 1, HealthStatus.CRIT.value: 2}
        worst = HealthStatus.OK.value
        for r in results:
            if order.get(r["status"], 0) > order[worst]:
                worst = r["status"]
        return worst