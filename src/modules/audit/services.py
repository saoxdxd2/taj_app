import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from src.modules.audit.models import AuditEvent
from src.database.transaction import transactional

logger = logging.getLogger(__name__)

def _serialize_for_json(obj: Any) -> Any:
    """Convert non-JSON-serializable types to serializable formats."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    return obj

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
            
        # Serialize data to ensure JSON compatibility
        before_serialized = _serialize_for_json(before_values) if before_values else None
        after_serialized = _serialize_for_json(after_values) if after_values else None
            
        event = AuditEvent(
            action=action,
            entity_name=entity_name,
            entity_id=entity_id,
            before_values=before_serialized,
            after_values=after_serialized,
            user_id=user_id,
            correlation_id=correlation_id
        )
        session.add(event)
        session.flush()  # Ensure created_at is populated
        logger.info(f"AUDIT [{action}] on {entity_name} ({entity_id}) | User: {user_id}")
        return event
