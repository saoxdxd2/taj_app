"""
Configuration of the website sync folder.

The sync folder is the meeting point between the ERP and the website:
- the ERP automatically writes website_catalog.json there on every
  product/stock change;
- the website (or a scheduled copy task) picks it up;
- price updates coming back are dropped there as price_updates.json
  and applied automatically by the ERP.
"""
import json
import logging
from pathlib import Path

from src.core.paths import CONFIG_DIR, BASE_DATA_DIR

logger = logging.getLogger(__name__)

_CONFIG_FILE = Path(CONFIG_DIR) / "website_sync.json"
DEFAULT_SYNC_FOLDER = Path(BASE_DATA_DIR) / "website_sync"


def get_sync_folder() -> Path:
    """Returns the configured sync folder, creating it if needed."""
    folder = DEFAULT_SYNC_FOLDER
    try:
        if _CONFIG_FILE.exists():
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            folder = Path(data.get("sync_folder", str(DEFAULT_SYNC_FOLDER)))
    except Exception as e:
        logger.warning(f"Could not read website sync config, using default: {e}")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def set_sync_folder(path) -> Path:
    """Persists the sync folder choice."""
    folder = Path(path)
    folder.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps({"sync_folder": str(folder)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Website sync folder set to: {folder}")
    return folder