"""Desktop <-> relay synchronization helpers.

Push: send the current ERP catalog to the relay (PUT /api/agent/catalog).
Pull: fetch the relay catalog snapshot (GET /api/catalog) for review.
Merge policy is deliberately conservative for Phase 0: pulled changes are
returned to the caller as a diff; nothing is written to the local DB
automatically. Automatic merging comes later, with per-field versioning.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.paths import CONFIG_DIR

logger = logging.getLogger(__name__)

STATE_FILE = CONFIG_DIR / "mobile_sync_state.json"


def load_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: Dict[str, Any]) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not save mobile sync state: %s", exc)


def push_catalog(context, client, version: Optional[int] = None) -> Dict[str, Any]:
    from .catalog import build_catalog_payload
    payload = build_catalog_payload(context)
    if version is not None:
        payload["version"] = version
    result = client.push_catalog(payload["version"], payload["products"])
    state = load_state()
    state["last_pushed_version"] = payload["version"]
    state["last_pushed_at"] = __import__("datetime").datetime.now().isoformat()
    save_state(state)
    logger.info("Pushed catalog version %s (%s products).", payload["version"], len(payload["products"]))
    return result


def pull_catalog(client, since_version: int = 0) -> Tuple[int, List[Dict[str, Any]]]:
    import httpx
    try:
        resp = client._client_get_catalog(since_version) if hasattr(client, "_client_get_catalog") else None
    except Exception:
        resp = None
    # Use the standard client method shape.
    url = f"{client.base_url}/api/catalog?version={since_version}"
    import httpx as _httpx
    with _httpx.Client(timeout=client._timeout) as c:
        r = c.get(url, headers=client._headers())
        if r.status_code == 304:
            return since_version, []
        r.raise_for_status()
        data = r.json()
    new_version = int(data.get("version", since_version))
    products = data.get("products", [])
    state = load_state()
    state["last_pulled_version"] = new_version
    state["last_pulled_at"] = __import__("datetime").datetime.now().isoformat()
    save_state(state)
    return new_version, products


def diff_catalog(local_products: List[Dict[str, Any]], remote_products: List[Dict[str, Any]]) -> Dict[str, List]:
    """Simple SKU-keyed diff: added / removed / changed (price/stock)."""
    local = {p["sku"]: p for p in local_products}
    remote = {p["sku"]: p for p in remote_products}
    added = [p for sku, p in remote.items() if sku not in local]
    removed = [p for sku, p in local.items() if sku not in remote]
    changed = []
    for sku in local.keys() & remote.keys():
        if local[sku] != remote[sku]:
            changed.append({"sku": sku, "local": local[sku], "remote": remote[sku]})
    return {"added": added, "removed": removed, "changed": changed}