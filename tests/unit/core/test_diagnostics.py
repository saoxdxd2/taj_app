"""Diagnostics export must survive a missing or read-only Desktop folder."""
import os
import zipfile

import src.core.diagnostics as diagnostics
from src.core.diagnostics import DiagnosticsManager


def test_diagnostics_falls_back_to_app_data(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    temp_dir = data_dir / "temp"
    temp_dir.mkdir(parents=True)

    monkeypatch.setattr(diagnostics, "BASE_DATA_DIR", data_dir)
    monkeypatch.setattr(diagnostics, "TEMP_DIR", temp_dir)
    monkeypatch.setattr(diagnostics, "DB_PATH", data_dir / "taj_froid.db")
    monkeypatch.setattr(diagnostics, "LOG_FILE_PATH", data_dir / "app.log")
    monkeypatch.setattr(diagnostics, "get_database_revision", lambda: "test-rev")

    # Simulate a locked-down profile with no usable Desktop folder.
    monkeypatch.setattr(
        diagnostics.os.path, "expanduser", lambda _path: str(tmp_path / "no-home")
    )

    bundle = DiagnosticsManager.create_diagnostic_bundle()
    try:
        assert os.path.isfile(bundle)
        assert os.path.dirname(bundle) == str(data_dir / "diagnostics")
        with zipfile.ZipFile(bundle) as archive:
            assert "system_info.txt" in archive.namelist()
    finally:
        if os.path.exists(bundle):
            os.remove(bundle)
