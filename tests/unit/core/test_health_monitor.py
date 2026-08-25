import os
import sqlite3
import time
import zipfile

from src.core.health_monitor import HealthMonitor, HealthStatus


def test_check_database_ok(tmp_path):
    """A healthy database passes integrity + FK checks."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE child (id INTEGER PRIMARY KEY, pid INTEGER REFERENCES parent(id))")
    conn.execute("INSERT INTO parent VALUES (1)")
    conn.execute("INSERT INTO child VALUES (1, 1)")
    conn.commit()
    conn.close()

    result = HealthMonitor.check_database(db)
    assert result["status"] == HealthStatus.OK.value
    assert "integrity ok" in result["detail"]


def test_check_database_detects_fk_violation(tmp_path):
    db = tmp_path / "bad.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE child (pid INTEGER REFERENCES parent(id))")
    conn.execute("INSERT INTO child VALUES (999)")  # orphan
    conn.commit()
    conn.close()

    result = HealthMonitor.check_database(db)
    assert result["status"] == HealthStatus.CRIT.value
    assert "foreign key" in result["detail"]


def test_check_database_missing_file(tmp_path):
    result = HealthMonitor.check_database(tmp_path / "nope.db")
    assert result["status"] == HealthStatus.CRIT.value


def test_check_disk_space_reports(tmp_path):
    result = HealthMonitor.check_disk_space(tmp_path)
    assert result["status"] in (HealthStatus.OK.value, HealthStatus.WARN.value)
    assert "GB free" in result["detail"]


def test_check_backups_fresh_and_stale(tmp_path):
    # Fresh backup -> OK
    fresh = tmp_path / "backup_fresh.zip"
    with zipfile.ZipFile(fresh, "w") as z:
        z.writestr("x.txt", "data")

    result = HealthMonitor.check_backups(tmp_path)
    assert result["status"] == HealthStatus.OK.value

    # Stale backup (in its own dir so it is the newest) -> WARN
    stale_dir = tmp_path / "stale"
    stale_dir.mkdir()
    stale = stale_dir / "backup_stale.zip"
    with zipfile.ZipFile(stale, "w") as z:
        z.writestr("y.txt", "data")
    old_ts = time.time() - (HealthMonitor.BACKUP_MAX_AGE_DAYS + 2) * 86400
    os.utime(stale, (old_ts, old_ts))

    result = HealthMonitor.check_backups(stale_dir)
    assert result["status"] == HealthStatus.WARN.value
    assert "older than" in result["detail"]

    # No backups at all -> WARN
    empty = tmp_path / "empty"
    empty.mkdir()
    result = HealthMonitor.check_backups(empty)
    assert result["status"] == HealthStatus.WARN.value


def test_overall_status_is_worst():
    results = [
        {"name": "a", "status": HealthStatus.OK.value, "detail": ""},
        {"name": "b", "status": HealthStatus.WARN.value, "detail": ""},
        {"name": "c", "status": HealthStatus.OK.value, "detail": ""},
    ]
    assert HealthMonitor.overall_status(results) == HealthStatus.WARN.value
    results.append({"name": "d", "status": HealthStatus.CRIT.value, "detail": ""})
    assert HealthMonitor.overall_status(results) == HealthStatus.CRIT.value