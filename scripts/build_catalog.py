"""
Builds the English reference catalog from the type-safe catalog.

The English catalog is *generated*, not hand-written, so the keys used by
the UI and the keys in resources/translations can never diverge. Run after
adding an Entry to src/i18n/catalog.py:

    python scripts/build_catalog.py

Also emits a context sidecar (en.context.json) holding each key's context
string, which is what a translator needs and what the previous
hand-maintained files never provided.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.i18n.catalog import tr  # noqa: E402
from src.i18n.translator import _translations_dir  # noqa: E402


def main() -> int:
    entries = tr.all_keys()
    by_module = defaultdict(dict)
    contexts = {}

    for entry in entries:
        # inventory.field.sku -> module 'inventory'
        module = entry.key.split(".", 1)[0]
        by_module[module][entry.key] = entry.key  # placeholder, filled below
        contexts[entry.key] = entry.context

    # Group by the owning module file name so each module owns its catalog,
    # as 12_LOCALIZATION_STANDARD.md requires.
    module_files = {
        "common": "common.json", "auth": "auth.json", "nav": "nav.json",
        "inventory": "inventory.json", "crm": "crm.json",
        "suppliers": "suppliers.json", "purchasing": "purchasing.json",
        "sales": "sales.json", "finance": "finance.json",
        "analytics": "analytics.json", "settings": "settings.json",
        "migration": "migration.json", "dashboard": "dashboard.json",
        "pagination": "pagination.json",
    }

    # The English text lives in a human-readable map keyed by catalog key.
    english = load_english_text()

    en_dir = _translations_dir() / "en"
    en_dir.mkdir(parents=True, exist_ok=True)

    for module, filename in module_files.items():
        keys = sorted(k for k in contexts if k.split(".", 1)[0] == module)
        payload = {k: english.get(k, k) for k in keys}
        path = en_dir / filename
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {path.relative_to(PROJECT_ROOT)} ({len(payload)} keys)")

    context_path = en_dir / "context.json"
    context_path.write_text(
        json.dumps(contexts, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {context_path.relative_to(PROJECT_ROOT)} ({len(contexts)} contexts)")

    absent = [k for k in contexts if k not in english]
    if absent:
        print(f"\nWARNING: {len(absent)} keys have no English text yet:", file=sys.stderr)
        for key in absent:
            print(f"  {key}", file=sys.stderr)
        return 1
    return 0


def load_english_text() -> dict:
    """
    Loads English strings from src/i18n/english.py.

    Keeping the text in a reviewed Python module (rather than generated
    JSON) means a translator edits one obvious place, and the generator
    still guarantees no key is ever missing from the shipped catalog.
    """
    try:
        from src.i18n.english import ENGLISH
        return dict(ENGLISH)
    except ImportError:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
