"""
Guard tests that make interface defects unrepresentable.

Two failure modes are targeted, and both are caused by hardcoded geometry:

1. Widgets overlapping or being clipped, because a fixed pixel size is
   wrong on a different DPI or after the text is translated (French is
   typically ~20% longer than English).
2. Translation keys drifting, so a screen silently reverts to English.

These run in CI, so a fixed width or a missing translation fails the
build instead of being discovered by a user.
"""
import pathlib
import re

import pytest

from src.i18n import tr, _, get_language, set_language, missing_keys
from src.i18n import validate_catalog
from src.i18n.translator import clear_cache

UI_DIR = pathlib.Path("src/ui")

# APIs that hardcode geometry. Each is a latent layout bug.
FORBIDDEN_CALLS = {
    "setFixedWidth": "use a layout + size policy, or scaled()/autosize_*",
    "setFixedHeight": "use autosize_* so the height follows the text",
    "setFixedSize": "use a layout + size policy",
    "setGeometry": "absolute geometry is ignored or misplaced by layouts",
}


def _ui_sources():
    return sorted(UI_DIR.rglob("*.py"))


# --- Layout guards ------------------------------------------------------

@pytest.mark.parametrize("api,advice", sorted(FORBIDDEN_CALLS.items()))
def test_no_hardcoded_geometry(api, advice):
    """
    No widget may pin itself to a pixel size.

    A fixed size is correct only for the DPI and language it was chosen
    for; it clips or overlaps everywhere else.
    """
    offenders = []
    for path in _ui_sources():
        rel = str(path).replace("\\", "/")
        # layout.py documents these APIs and must name them in prose; a
        # comment or docstring mention is not a call.
        if rel.endswith("ui/layout.py"):
            continue
        for i, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if api in line and not line.strip().startswith("#"):
                offenders.append(f"{rel}:{i}: {line.strip()[:70]}")
    assert not offenders, (
        f"{api} used in {len(offenders)} place(s); {advice}\n"
        + "\n".join(offenders)
    )


def test_tables_elide_instead_of_overflowing():
    """
    Every QTableWidget must degrade gracefully.

    A table that cannot elide forces a horizontal scrollbar, which is
    how long product names end up half-hidden.
    """
    offenders = []
    for path in _ui_sources():
        rel = str(path).replace("\\", "/")
        # theme.py holds the stylesheet text and models/ holds table
        # subclasses; neither constructs a QTableWidget.
        if rel.endswith("ui/theme.py") or "/ui/models/" in rel:
            continue
        text = path.read_text(encoding="utf-8")
        if "QTableWidget" not in text:
            continue
        if "setTextElideMode" not in text and "add_elided_columns" not in text:
            offenders.append(rel)
    assert not offenders, (
        "tables without elide handling (use layout.add_elided_columns):\n"
        + "\n".join(offenders)
    )


# --- Localization guards ------------------------------------------------

def test_catalog_keys_are_unique():
    """Two Entries sharing a key would silently overwrite each other."""
    keys = [e.key for e in tr.all_keys()]
    duplicates = {k for k in keys if keys.count(k) > 1}
    assert not duplicates, f"duplicate catalog keys: {sorted(duplicates)}"


def test_catalog_keys_follow_the_naming_convention():
    """module.section.element, per 12_LOCALIZATION_STANDARD.md."""
    invalid = [
        e.key for e in tr.all_keys()
        if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+){1,3}", e.key)
    ]
    assert not invalid, f"keys not matching module.section.element: {invalid}"


def test_every_key_has_context_for_translators():
    """
    A key with no context forces a translator to guess how the word is
    used, which is where wrong terminology comes from.
    """
    missing = [e.key for e in tr.all_keys() if not e.context.strip()]
    assert not missing, f"keys without translator context: {missing}"


def test_french_catalog_is_complete():
    """A missing French string must fail CI, not ship as English."""
    gaps = missing_keys("fr")
    assert not gaps, (
        f"{len(gaps)} untranslated key(s) for French:\n" + "\n".join(gaps[:20])
    )


def test_catalog_placeholders_match_reference():
    """
    A translation that drops a placeholder would print a literal
    '{amount}' to a user, or raise at render time.
    """
    problems = validate_catalog()
    assert not problems, "catalog problems:\n" + "\n".join(problems)


def test_lookup_falls_back_to_english_not_blank():
    """An unknown key degrades to readable text, never an empty control."""
    clear_cache()
    try:
        assert _("definitely.not.a.real.key") == "definitely.not.a.real.key"
    finally:
        clear_cache()


def test_language_switching_round_trips():
    assert set_language("fr") is True
    assert get_language() == "fr"
    assert set_language("en") is True
    assert set_language("zz") is False  # unsupported languages are refused
