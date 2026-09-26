"""Translation runtime: catalog loading, lookup, and validation."""
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "fr")

# Placeholders such as {name} or {amount}
_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

# Sidecar files that live beside the catalogs but are not UI text.
_NON_CATALOG_FILES = {"context.json"}

_lock = threading.Lock()
_state = {
    "language": DEFAULT_LANGUAGE,
    # language -> {key: text}
    "catalogs": {},
    # The English catalog doubles as the reference for validation.
    "reference": {},
}


def _translations_dir() -> Path:
    """
    Resolves the translations root.

    Overridable with TAJ_TRANSLATIONS_DIR so tests can point at a
    temporary catalog without touching the shipped resources.
    """
    override = os.environ.get("TAJ_TRANSLATIONS_DIR")
    if override:
        return Path(override)
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "resources" / "translations"


def _load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        # A malformed catalog must be loud: silently ignoring it would
        # ship an English-only interface with no explanation.
        logger.error(f"Malformed translation file {path}: {exc}")
        return {}
    return data if isinstance(data, dict) else {}


def _flatten(prefix: str, value, out: Dict[str, str]) -> None:
    """Flattens {"sales": {"total": "x"}} into {"sales.total": "x"}."""
    if isinstance(value, dict):
        for sub_key, sub_value in value.items():
            _flatten(f"{prefix}.{sub_key}", sub_value, out)
    elif isinstance(value, str):
        out[prefix] = value
    else:
        logger.warning(f"Ignoring non-string translation for '{prefix}': {value!r}")


def _load_language(language: str) -> dict:
    """Loads and flattens every module catalog for one language."""
    root = _translations_dir() / language
    flat: Dict[str, str] = {}
    if not root.is_dir():
        logger.warning(f"No translations directory for language '{language}'")
        return flat

    for json_file in sorted(root.glob("*.json")):
        # context.json holds translator notes, not UI text. Loading it as a
        # catalog would put the English *context* ("Unexpected
        # authentication error") in place of the real string.
        if json_file.name in _NON_CATALOG_FILES:
            continue
        for key, value in _load_json(json_file).items():
            _flatten(key, value, flat)
    return flat


def _load_all() -> None:
    """(Re)loads every supported language. Called once, then cached."""
    with _lock:
        reference = _load_language(DEFAULT_LANGUAGE)
        catalogs = {DEFAULT_LANGUAGE: reference}
        for language in SUPPORTED_LANGUAGES:
            if language != DEFAULT_LANGUAGE:
                catalogs[language] = _load_language(language)
        _state["catalogs"] = catalogs
        _state["reference"] = reference


def get_language() -> str:
    """Returns the active language code."""
    if not _state["catalogs"]:
        _load_all()
    return _state["language"]


def available_languages() -> List[str]:
    """Returns the language codes that can be selected."""
    return list(SUPPORTED_LANGUAGES)


def set_language(language: str) -> bool:
    """
    Switches the active language. Returns False for an unsupported code.

    Per the localization standard the UI is expected to be restarted
    after a change, so this does not attempt a live repaint of every
    widget; widgets read the language at construction time.
    """
    if language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language '{language}'")
        return False
    with _lock:
        _state["language"] = language
    return True


def clear_cache() -> None:
    """Forces a reload from disk. Used by tests."""
    with _lock:
        _state["catalogs"] = {}
        _state["language"] = DEFAULT_LANGUAGE

def clear_cache() -> None:
    """Forces a reload from disk. Used by tests."""
    with _lock:
        _state["catalogs"] = {}
        _state["language"] = DEFAULT_LANGUAGE


def translate(key: str, **kwargs) -> str:
    """
    Returns the text for `key` in the active language.

    Falls back to the English reference and finally to the key itself, so
    a missing translation degrades to readable English rather than an
    empty label. Placeholders are substituted last, and only when the
    caller supplied them.
    """
    if not _state["catalogs"]:
        _load_all()

    catalog = _state["catalogs"].get(_state["language"], {})
    text = catalog.get(key)
    if text is None:
        text = _state["reference"].get(key)
    if text is None:
        # Last resort: surface the key so the gap is visible in the UI
        # instead of showing a blank control.
        text = key

    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError) as exc:
            logger.error(f"Bad placeholders for key '{key}': {exc}")
            return text
    return text


def missing_keys(language: Optional[str] = None) -> List[str]:
    """
    Returns reference keys with no translation for `language`.

    Asserted empty by the test suite, so an untranslated string fails CI
    rather than shipping as English.
    """
    if not _state["catalogs"]:
        _load_all()
    language = language or _state["language"]
    if language == DEFAULT_LANGUAGE:
        return []
    catalog = _state["catalogs"].get(language, {})
    return sorted(k for k in _state["reference"] if not catalog.get(k))


def validate_catalog() -> List[str]:
    """
    Checks every translation for structural problems.

    Reports a translation whose placeholders differ from the English
    reference, which would otherwise raise KeyError at render time or
    print a literal '{amount}' to the user.
    """
    problems: List[str] = []
    if not _state["catalogs"]:
        _load_all()

    reference = _state["reference"]
    for language, catalog in _state["catalogs"].items():
        if language == DEFAULT_LANGUAGE:
            continue
        for key, text in catalog.items():
            expected = reference.get(key)
            if expected is None:
                problems.append(f"[{language}] '{key}' is not in the English catalog")
                continue
            want = set(_PLACEHOLDER.findall(expected))
            got = set(_PLACEHOLDER.findall(text))
            if want != got:
                problems.append(
                    f"[{language}] '{key}' placeholders {sorted(got)} "
                    f"do not match reference {sorted(want)}"
                )
    return problems


def unused_keys(used: Iterable[str]) -> List[str]:
    """Returns catalog keys that no module references. Housekeeping aid."""
    used_set = set(used)
    if not _state["catalogs"]:
        _load_all()
    return sorted(k for k in _state["reference"] if k not in used_set)
