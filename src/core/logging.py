import os
import re
import sys
from loguru import logger
from src.core.paths import LOG_FILE_PATH

# Patterns for values that must never reach a log file. `diagnose=True`
# already leaks local variables, so production additionally scrubs
# anything that looks like a credential.
_SENSITIVE_PATTERNS = (
    (re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*\S+"), r"\1=***"),
    (re.compile(r"(?i)\b(secret|token|api[_-]?key)\b\s*[:=]\s*\S+"), r"\1=***"),
    # An Argon2 hash: $argon2id$v=19$m=...,t=...,p=...$salt$digest
    (re.compile(r"\$argon2[^\s\"']+"), "***"),
)


def redact_sensitive(text: str) -> str:
    """
    Removes credentials from a log message.

    Used in production only: in development the raw values are kept because
    that is exactly what makes a local traceback useful.
    """
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _redact_record(record) -> bool:
    """
    Loguru filter that scrubs credentials from a record before formatting.

    A filter must return True to keep the record; the in-place mutation of
    record["message"] is what performs the redaction.
    """
    record["message"] = redact_sensitive(record["message"])
    return True


def _read_config_environment() -> str:
    """
    Reads `environment` from the application settings.

    Split out from _is_development so the failure path is testable.
    """
    from src.core.config import settings
    return settings.environment


def _is_development() -> bool:
    """
    Returns True when running in a development environment.

    Defaults to development when the environment cannot be determined, so
    a missing or unreadable setting never silently silences logging. Also
    honours the TAJ_ENVIRONMENT environment variable, which lets a
    packaged production build be run in verbose mode without a .env file.
    """
    env = os.environ.get("TAJ_ENVIRONMENT", "").strip()
    if not env:
        try:
            env = _read_config_environment()
        except Exception:
            # pydantic-settings missing or .env unreadable: assume dev so
            # logs are never accidentally silenced.
            return True
    return env.strip().lower() in ("development", "dev", "local", "debug")


def setup_logging():
    """
    Configures enterprise-grade logging for the application.
    Removes the default handler, adds a file handler with rotation and retention.
    Also hooks into sys.excepthook to catch unhandled UI exceptions.

    Rotation size and retention are read from the system settings so they can
    be changed without a code change; if the database cannot be read, the
    documented defaults (10 MB / 30 days) are used.

    Verbosity is environment-aware (src.core.config.settings.environment):

    - development: console handler at DEBUG, full backtraces and `diagnose`
      (local variable values), because that is what makes a local
      traceback useful.
    - production: no console handler, file handler at WARNING with
      `backtrace` and `diagnose` disabled, plus a redaction patch so a
      credential can never be written to disk.
    """
    # Remove default stderr handler to prevent console clutter if not needed
    # or keep it for debugging. We'll remove and add a clean one.
    logger.remove()

    from src.core.backup import _configured_int
    from src.modules.settings.models import SettingKey

    is_dev = _is_development()

    rotation_mb = _configured_int(SettingKey.LOG_ROTATION_SIZE_MB, 10)
    retention_days = _configured_int(SettingKey.LOG_RETENTION_DAYS, 30)
    
    # Add console logger (helpful in dev; noisy and unnecessary in production)
    if is_dev:
        logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
    
    # Add rotating file logger in the %LOCALAPPDATA% directory
    # In production a filter scrubs credentials on their way to disk. The
    # filter runs per record before formatting, which is the documented
    # loguru API for inspecting a record (logger.patch is not sufficient
    # here because the message is already rendered by then).
    logger.add(
        str(LOG_FILE_PATH),
        rotation=f"{rotation_mb} MB",       # Configurable: log.rotation.size_mb
        retention=f"{retention_days} days",  # Configurable: log.retention.days
        compression="zip",      # Compress rotated logs
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG" if is_dev else "WARNING",
        backtrace=is_dev,       # Extended traceback (dev only: verbose)
        diagnose=is_dev,        # Local variable values (dev only: may leak data)
        filter=None if is_dev else _redact_record,
    )

    # Global unhandled exception hook
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    
    logger.info(f"Enterprise logging initialized ({'development' if is_dev else 'production'} mode).")
