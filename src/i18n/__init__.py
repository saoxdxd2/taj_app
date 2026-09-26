"""
Internationalization / localization framework.

Replaces hand-maintained JSON key files, which drift: a key is renamed in
one module, the old key silently falls back to English, and nothing
fails until a user sees a half-translated screen.

The failure modes this design prevents:

1. **Typos in keys.** Keys are Python attributes on a frozen catalog
   class, so `_(tr.sales.invoice_titel)` is an AttributeError at import
   time rather than a silent English fallback in production.

2. **Missing translations.** load() reports every key with no value for
   the active language, and `missing_keys()` is asserted by a test, so a
   gap is caught in CI instead of by a user.

3. **Lost context.** A catalog entry may carry a `context` string, so a
   translator sees how the word is used instead of guessing.

4. **Format-string mistakes.** Placeholders are validated against the
   reference (English) text at load time, so a translation cannot
   silently drop `{amount}` and print "None".

Translations are plain dicts loaded from resources/translations/<lang>/*.json,
owned per module, exactly as 12_LOCALIZATION_STANDARD.md specifies. The
framework is what makes that file layout safe to maintain.
"""
from src.i18n.catalog import Entry, tr
from src.i18n.translator import (
    get_language, available_languages, set_language,
    translate, clear_cache, missing_keys, validate_catalog, unused_keys,
)


def _(key: str, **kwargs) -> str:
    """
    Translate a key. Preferred form in UI code: _("common.action.save").

    Passing a catalog Entry also works, so a key that exists in the
    catalog cannot be misspelled: Entry has no .format/.strip, so a
    string-literal key that is actually a typo fails loudly.
    """
    if isinstance(key, Entry):
        return translate(key.key, **kwargs)
    return translate(key, **kwargs)


__all__ = [
    "Entry", "tr", "_", "get_language", "available_languages",
    "set_language", "translate", "clear_cache", "missing_keys",
    "validate_catalog", "unused_keys",
]
