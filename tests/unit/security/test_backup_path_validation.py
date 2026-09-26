"""
Tests for backup-restore path validation.

A restore overwrites the live database, so an arbitrary path must be
refused before anything is opened.
"""
import os
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
