"""
Tests for backup-restore path validation.

A restore overwrites the live database, so an arbitrary path must be
refused before anything is opened.
"""
import os
import sqlite3
import zipfile

import pytest

from src.core.backup import BackupManager


def _make_zip(path, name="taj_froid.db", content=b"SQLite format 3\x00"):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(name, content)
    return str(path)


def test_accepts_a_real_zip(tmp_path):
    path = _make_zip(tmp_path / "backup.zip")
    assert BackupManager._is_valid_backup_path(path) is True


def test_rejects_missing_file(tmp_path):
    assert BackupManager._is_valid_backup_path(
        str(tmp_path / "nope.zip")
    ) is False


def test_rejects_empty_path():
    assert BackupManager._is_valid_backup_path("") is False


def test_rejects_non_zip_extension(tmp_path):
    """A .db or .exe renamed path must not be accepted."""
    path = tmp_path / "backup.db"
    path.write_bytes(b"not a zip")
    assert BackupManager._is_valid_backup_path(str(path)) is False


def test_rejects_zip_extension_that_is_not_a_zip(tmp_path):
    """
    The extension alone is not enough: the content must really be a zip,
    otherwise a crafted file passes the name check.
    """
    path = tmp_path / "evil.zip"
    path.write_bytes(b"PK not really a zip")
    assert BackupManager._is_valid_backup_path(str(path)) is False


def test_rejects_directory(tmp_path):
    assert BackupManager._is_valid_backup_path(str(tmp_path)) is False


@pytest.mark.skipif(
    not hasattr(os, "symlink"), reason="symlinks unsupported on this platform"
)
def test_rejects_symlink(tmp_path):
    """A symlink with a backup-looking name must be refused."""
    real = _make_zip(tmp_path / "real.zip")
    link = tmp_path / "looks_like_backup.zip"
    try:
        os.symlink(real, link)
    except OSError:
        pytest.skip("symlink creation not permitted")
    assert BackupManager._is_valid_backup_path(str(link)) is False


def test_restore_refuses_an_invalid_path(tmp_path):
    """The guard must run inside restore_backup, not just as a helper."""
    bad = tmp_path / "not_a_backup.zip"
    bad.write_bytes(b"nope")
    with pytest.raises(ValueError, match="Refusing to restore"):
        BackupManager.restore_backup(str(bad))


def test_restore_archive_must_contain_the_database_member(tmp_path):
    """A zip with the wrong member name is not a backup."""
    path = _make_zip(tmp_path / "wrong.zip", name="something_else.db")
    with pytest.raises(ValueError, match="taj_froid.db"):
        BackupManager._validate_restore_archive(path)


def test_restore_refuses_a_zip_that_is_not_a_sqlite_database(tmp_path):
    """A valid zip with arbitrary bytes must not replace the live DB."""
    path = _make_zip(tmp_path / "fake.zip", content=b"not a database")
    with pytest.raises(ValueError, match="SQLite database"):
        BackupManager.restore_backup(path)


def test_sqlite_validation_accepts_a_healthy_database(tmp_path):
    db_path = tmp_path / "healthy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    BackupManager._validate_sqlite_database(str(db_path))


def test_sqlite_validation_rejects_corruption(tmp_path):
    db_path = tmp_path / "corrupt.db"
    db_path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 64)
    with pytest.raises(ValueError, match="unreadable|integrity"):
        BackupManager._validate_sqlite_database(str(db_path))


def test_list_backups_lists_only_restorable_zips(monkeypatch, tmp_path):
    old = _make_zip(tmp_path / "old.zip")
    new = _make_zip(tmp_path / "new.zip")
    (tmp_path / "legacy.db").write_bytes(b"SQLite format 3\x00")
    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))
    monkeypatch.setattr("src.core.backup.BACKUP_DIR", str(tmp_path))

    assert BackupManager.list_backups() == [new, old]


def test_retention_policy_never_deletes_every_backup(monkeypatch, tmp_path):
    """A negative/corrupt retention setting must not wipe all backups."""
    for name in ("a.zip", "b.zip", "c.zip"):
        _make_zip(tmp_path / name)
    monkeypatch.setattr("src.core.backup.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("src.core.backup._configured_int", lambda *a, **k: -5)

    BackupManager._apply_retention_policy()

    assert len(BackupManager.list_backups()) == 1
