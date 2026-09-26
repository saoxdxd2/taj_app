"""
Tests for input sanitization.

These guard the boundary where user-supplied text becomes markup: a
product or customer name typed by a user must never be interpreted as
HTML, and must never smuggle control sequences into a log or PDF.
"""
import pytest

from src.security.sanitizers import (
    sanitize_text, sanitize_username, validate_password_strength,
)


# --- Text sanitization --------------------------------------------------

def test_escapes_html_tags():
    """A product name like <script> must render as literal text."""
    out = sanitize_text("<script>alert('x')</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_escapes_quotes_for_attribute_context():
    out = sanitize_text('" onerror="alert(1)')
    assert '"' not in out
    assert "&quot;" in out


def test_escapes_ampersand():
    assert sanitize_text("Tom & Jerry") == "Tom &amp; Jerry"


def test_strips_ansi_escape_sequences():
    """ANSI codes would corrupt a log file or a terminal."""
    out = sanitize_text("\x1b[31mred\x1b[0m")
    assert "\x1b" not in out
    assert "red" in out


def test_strips_control_characters():
    out = sanitize_text("bad\x00name\x07")
    assert "\x00" not in out
    assert "\x07" not in out
    assert "badname" in out


def test_preserves_newlines_and_tabs():
    """Multi-line descriptions must survive sanitization."""
    out = sanitize_text("line1\nline2\tindented")
    assert "line1" in out and "line2" in out and "indented" in out


def test_none_becomes_empty_string():
    """Callers can render the result without a None check."""
    assert sanitize_text(None) == ""


def test_truncates_to_max_length():
    assert len(sanitize_text("abcdefghij", max_length=4)) == 4


def test_ordinary_text_is_unchanged():
    plain = "Climatiseur Split 12000 BTU"
    assert sanitize_text(plain) == plain


# --- Username sanitization ----------------------------------------------

def test_username_is_stripped():
    assert sanitize_username("  admin  ") == "admin"


def test_username_drops_control_characters():
    assert "\x00" not in sanitize_username("ad\x00min")


def test_username_is_length_capped_to_column_width():
    """The column is String(50); a longer name could not be stored."""
    assert len(sanitize_username("u" * 200)) == 50


def test_username_of_none_is_empty():
    assert sanitize_username(None) == ""


# --- Password strength --------------------------------------------------

def test_accepts_a_compliant_password():
    assert validate_password_strength("Secret123") == "Secret123"


@pytest.mark.parametrize("password,missing", [
    ("abc", "at least 8"),
    ("alllowercase", "uppercase"),
    ("ALLUPPERCASE1", "lowercase"),
    ("NoDigitsHere", "digit"),
])
def test_rejects_weak_passwords(password, missing):
    with pytest.raises(ValueError, match=missing):
        validate_password_strength(password)


def test_rejects_empty_password():
    with pytest.raises(ValueError):
        validate_password_strength("")
