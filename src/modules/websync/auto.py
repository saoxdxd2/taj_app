"""
Automatic website synchronization hooks.

- After any commit that touches Product or StockLevel, the website
  catalog is silently regenerated in the sync folder.
- process_pending_updates() applies price_updates.json dropped by the
  website and archives it.

Call setup_auto_sync() once at application startup.
"""
import logging

from sqlalchemy import event
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_setup_done = False


def setup_auto_sync() -> None:
    """
    Installs the ORM listeners (idempotent) and runs one immediate
    export + pending-update pass so both sides start in sync.
    """
    global _setup_done
    if _setup_done:
        return
    _setup_done = True

    from src.modules.inventory.models import Product, StockLevel
    from src.modules.websync.services import WebsiteSyncService

    def _mark_dirty(mapper, connection, target):
        session = Session.object_session(target)
        if session is not None:
            session.info["websync_dirty"] = True

    for cls in (Product, StockLevel):
        event.listen(cls, "after_insert", _mark_dirty)
        event.listen(cls, "after_update", _mark_dirty)
        event.listen(cls, "after_delete", _mark_dirty)

    @event.listens_for(Session, "after_commit")
    def _after_commit(session):
        if session.info.pop("websync_dirty", False):
            WebsiteSyncService.auto_export_catalog()

    # Bring both sides in sync right now
    WebsiteSyncService.process_pending_updates()
    WebsiteSyncService.auto_export_catalog()
    logger.info("Website auto-sync initialized.")