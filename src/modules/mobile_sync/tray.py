"""Desktop tray service for mobile sync.

Runs the mobile sync agent even when the ERP window is closed. Shares
the same database and config as the main application. Started by
``mobile_tray.py`` at the repository root.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

# Ensure the repo root is on sys.path when launched directly.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.context import RequestContext
from src.core.session import CurrentSession
from src.database.session import SessionLocal
from src.modules.authentication.bootstrap import initialize_security
from src.modules.mobile_sync.crypto import load_agent_token
from src.modules.mobile_sync.worker import TraySyncWorker

logger = logging.getLogger("mobile_tray")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

CONFIG_FILE = ROOT / "config" / "mobile_relay.json" if False else None


def _load_relay_url() -> str:
    import json
    from src.core.paths import CONFIG_DIR
    try:
        data = json.loads((CONFIG_DIR / "mobile_relay.json").read_text(encoding="utf-8"))
        return data.get("relay_url", "")
    except (OSError, ValueError):
        return os.environ.get("TAJ_MOBILE_RELAY_URL", "")


def _init_session():
    from src.core.migrations import apply_migrations
    apply_migrations()
    with SessionLocal() as session:
        initialize_security(session)
        session.commit()
    # Start as local administrator.
    from src.core.session import CurrentSession as CS
    from src.modules.authentication.models import Role, User
    from src.modules.authentication.services import AuthenticationService
    with SessionLocal() as session:
        admin_role = session.query(Role).filter(Role.name == AuthenticationService.ADMIN_ROLE).first()
        admins = session.query(User).filter(User.role_id == admin_role.id).order_by(User.id).all()
        user = next((u for u in admins if u.is_active), admins[0] if admins else None)
        if user is None:
            raise RuntimeError("No administrator account found.")
        CS.initialize(RequestContext(
            user_id=str(user.id), username=user.username, role=user.role.name,
            permissions={p.name for p in user.role.permissions}, workstation="Tray",
        ))


def run_tray():
    import pystray
    from PIL import Image, ImageDraw

    relay_url = _load_relay_url()
    context = CurrentSession.get_context() if False else None
    _init_session()
    context = CurrentSession.get_context()

    worker = None
    if relay_url and load_agent_token():
        worker = TraySyncWorker(relay_url, context)
        worker.start()
        logger.info("Mobile sync worker started against %s", relay_url)
    else:
        logger.warning("Relay URL or agent token missing; agent not started.")

    # Simple icon.
    img = Image.new("RGB", (64, 64), color=(31, 58, 95))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "M", fill=(255, 255, 255))

    stop_ui = threading.Event()

    def _refresh_title():
        """Surface the latest SyncStatus on the existing tray tooltip."""
        while not stop_ui.wait(2.0):
            if worker is None:
                continue
            try:
                icon.title = "TAJ Mobile Sync — " + worker.get_status().compact()
            except Exception:  # noqa: BLE001 - icon may be tearing down
                logger.debug("Could not update tray status title.")

    def on_quit(icon, item):
        stop_ui.set()
        if worker is not None:
            worker.stop()
            worker.wait(5000)
        icon.stop()

    icon = pystray.Icon("taj_mobile_tray", img, "TAJ Mobile Sync", menu=pystray.Menu(
        pystray.MenuItem("Quit", on_quit),
    ))
    ui_thread = threading.Thread(target=_refresh_title, name="mobile-sync-tray-status", daemon=True)
    ui_thread.start()
    try:
        icon.run()
    finally:
        stop_ui.set()
        if worker is not None:
            worker.stop()


if __name__ == "__main__":
    run_tray()