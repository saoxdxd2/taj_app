import logging
from typing import Optional, Dict, Any
from src.modules.audit.models import AuditEvent
from src.database.transaction import transactional

logger = logging.getLogger(__name__)

class AuditService:
    """
    Business service handling immutable audit logging.
    """

    @staticmethod
    @transactional
    def record_event(session, action: str, entity_name: str, entity_id: Optional[str] = None,
                     before_values: Optional[Dict[str, Any]] = None,
                     after_values: Optional[Dict[str, Any]] = None,
                     user_id: Optional[int] = None,
                     correlation_id: Optional[str] = None) -> AuditEvent:
        """
        Creates an immutable audit event.
        Does not allow editing or deletion per 15_SECURITY_STANDARD.md.
        """
        if not action or not entity_name:
            raise ValueError("Action and entity_name are mandatory for an audit event.")
            
        event = AuditEvent(
            action=action,
            entity_name=entity_name,
            entity_id=entity_id,
            before_values=before_values,
            after_values=after_values,
            user_id=user_id,
            correlation_id=correlation_id
        )
        session.add(event)
        logger.info(f"AUDIT [{action}] on {entity_name} ({entity_id}) | User: {user_id}")
        return event
