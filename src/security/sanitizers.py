"""Input sanitization helpers.

User-supplied text is displayed in Qt widgets, exported to the website
catalog, and written into PDFs. Anything that could be interpreted as
markup or a control sequence must be neutralised at that boundary.

This is deliberately dependency-free (stdlib `html`), so it is available
during early startup and in the diagnostic path where third-party imports
are not guaranteed.
"""
import html
import re
from typing import Optional

# ANSI escape sequences, which would corrupt a log file or a terminal.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Control characters other than tab/newline/carriage-return.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value: Optional[str], max_length: Optional[int] = None) -> str:
    """
    Returns text safe to render in a UI label or embed in a document.

    Escapes HTML-significant characters and strips control characters.
    Returns "" for None, so callers can render the result unconditionally.
    """
    if value is None:
        return ""
    text = str(value)
    text = _ANSI_RE.sub("", text)
    text = _CONTROL_RE.sub("", text)
    text = html.escape(text, quote=True)
    if max_length is not None and len(text) > max_length:
        text = text[:max_length]
    return text


def sanitize_username(value: Optional[str]) -> str:
    """
    Normalizes a username: strips, removes control characters, and caps the
    length at the column width (50) so it can never be unpersistable.
    """
    if value is None:
        return ""
    text = _ANSI_RE.sub("", str(value))
    text = _CONTROL_RE.sub("", text).strip()
    return text[:50]


def validate_password_strength(password: str, min_length: int = 8) -> str:
    """
    Enforces password complexity, returning the password when acceptable.

    Requires a minimum length plus at least one lowercase letter, one
    uppercase letter, and one digit. Raises ValueError with a description
    of what is missing otherwise.

    Note: this is applied on create and change, never on login, so existing
    accounts (including the default 'admin') are never locked out by a rule
    introduced after they were created.
    """
    if not password or len(password) < min_length:
        raise ValueError(f"Password must be at least {min_length} characters long.")

    checks = (
        (any(c.islower() for c in password), "a lowercase letter"),
        (any(c.isupper() for c in password), "an uppercase letter"),
        (any(c.isdigit() for c in password), "a digit"),
    )
    missing = [description for ok, description in checks if not ok]
    if missing:
        raise ValueError("Password must contain " + ", ".join(missing) + ".")
    return password
