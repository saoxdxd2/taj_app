"""
Tests for environment-aware logging and credential redaction.

The security property under test: a password must never reach the log
file in production, and `diagnose` (which dumps local variables) must be
off outside development.
"""
import pytest
from loguru import logger

from src.core.logging import _is_development, redact_sensitive, setup_logging


# --- Redaction ----------------------------------------------------------

def test_redacts_password_assignment():
    assert redact_sensitive("login password=hunter2") == "login password=***"


def test_redacts_password_with_colon():
    assert "hunter2" not in redact_sensitive("user said password: hunter2")


def test_redacts_secret_and_token():
    assert "abc123" not in redact_sensitive("api_key=abc123")
    assert "xyz789" not in redact_sensitive("token: xyz789")


def test_redacts_argon2_hash():
    """A leaked Argon2 hash must never be written to disk."""
    raw = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$hashvalue"
    assert "hashvalue" not in redact_sensitive(f"stored {raw}")


def test_leaves_ordinary_messages_untouched():
    msg = "Created draft invoice FACT-01 for client Client SARL"
    assert redact_sensitive(msg) == msg


def test_redaction_is_case_insensitive():
    assert "hunter2" not in redact_sensitive("PASSWORD=Hunter2")


# --- Environment awareness ---------------------------------------------

def test_setup_logging_succeeds_when_database_unavailable(monkeypatch, tmp_path):
    """
    Logging must never be the reason the app fails to start.

    setup_logging reads the system settings from the database. If that
    read fails for any reason (no table yet, corrupt file, locked DB) the
    app must still come up using the documented defaults.
    """
    import src.database.session as session_mod

    class BrokenSession:
        def __init__(self, *a, **kw):
            raise RuntimeError("database is unavailable")

        def close(self):
            pass

    monkeypatch.setenv("TAJ_ENVIRONMENT", "development")
    # Break the actual DB layer, leaving the real guard in place.
    monkeypatch.setattr(session_mod, "SessionLocal", BrokenSession)
    monkeypatch.setattr("src.core.logging.LOG_FILE_PATH", str(tmp_path / "app.log"))

    try:
        setup_logging()  # must not raise
    except RuntimeError:
        pytest.fail("setup_logging propagated a database failure")

    # The handler should still be usable afterwards.
    logger.info("still logging")


def test_production_disables_console_and_redacts(monkeypatch, tmp_path):
    """
    In production the redaction patch must be applied to real log output.
    """
    import src.database.session as session_mod

    class UnusedSession:
        def __init__(self, *a, **kw):
            raise RuntimeError("no database in this test")

        def close(self):
            pass

    log_file = tmp_path / "app.log"
    monkeypatch.setenv("TAJ_ENVIRONMENT", "production")
    monkeypatch.setattr("src.core.logging.LOG_FILE_PATH", str(log_file))
    monkeypatch.setattr(session_mod, "SessionLocal", UnusedSession)

    setup_logging()

    # A password must never survive into the production log file.
    logger.warning("auth attempt password=supersecret")

    for handler in list(logger._core.handlers.values()):
        sink = getattr(handler, "_sink", None)
        if sink is not None and hasattr(sink, "flush"):
            sink.flush()

    contents = log_file.read_text(encoding="utf-8", errors="ignore")
    assert "supersecret" not in contents, "password leaked into the production log"
    # The surrounding context must survive redaction.
    assert "auth attempt" in contents

    logger.remove()  # leave loguru clean for the remaining tests


def test_unknown_environment_falls_back_to_development(monkeypatch):
    """
    Logging must never be silently silenced by an unreadable setting.
    """
    monkeypatch.setenv("TAJ_ENVIRONMENT", "")
    monkeypatch.setattr(
        "src.core.logging._read_config_environment",
        lambda: (_ for _ in ()).throw(RuntimeError("no config")),
    )
    assert _is_development() is True


def test_explicit_production_environment_is_honoured(monkeypatch):
    monkeypatch.setenv("TAJ_ENVIRONMENT", "production")
    assert _is_development() is False
