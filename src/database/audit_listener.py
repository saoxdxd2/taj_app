from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import get_history
import logging
from typing import Dict, Any

from src.core.session import CurrentSession
from src.modules.audit.models import AuditEvent

logger = logging.getLogger(__name__)

def _get_model_dict(obj, is_deleted=False) -> Dict[str, Any]:
    """Helper to convert model attributes to a dictionary."""
    data = {}
    for c in obj.__table__.columns:
        # If object is deleted, we might need to get the old value
        history = get_history(obj, c.key)
        if is_deleted:
            # If deleted, current value might still be in object dict, or in history.deleted
            if history.has_changes():
                data[c.key] = history.deleted[0] if history.deleted else None
            else:
                data[c.key] = getattr(obj, c.key, None)
        else:
            data[c.key] = getattr(obj, c.key, None)
            
        # Convert non-serializable types to string (e.g. datetimes, UUIDs, Enums)
        if data[c.key] is not None:
            if hasattr(data[c.key], 'value'): # For Enums
                data[c.key] = data[c.key].value
            elif not isinstance(data[c.key], (int, float, str, bool, list, dict)):
                data[c.key] = str(data[c.key])
    return data

@event.listens_for(Session, "before_flush")
def audit_before_flush(session: Session, flush_context, instances):
    """
    Automatically tracks changes for models with __audit__ = True.
    Must be fast and not crash the transaction.
    """
    try:
        context = CurrentSession.get_context()
        user_id = int(context.user_id) if context and context.user_id else None
        correlation_id = context.correlation_id if context else None
    except Exception as e:
        # Core operations without RequestContext might fail to get user
        logger.warning(f"Audit: Could not retrieve RequestContext: {e}")
        user_id = None
        correlation_id = None

    new_audit_events = []

    # Process Inserts
    for obj in session.new:
        if not getattr(type(obj), "__audit__", False):
            continue
            
        after_vals = _get_model_dict(obj)
        event_record = AuditEvent(
            action="CREATE",
            entity_name=type(obj).__name__,
            entity_id=str(getattr(obj, "id", "")),
            before_values=None,
            after_values=after_vals,
            user_id=user_id,
            correlation_id=correlation_id
        )
        new_audit_events.append(event_record)

    # Process Updates
    for obj in session.dirty:
        if not getattr(type(obj), "__audit__", False):
            continue
            
        # Only log if there's actually a change in columns
        if not session.is_modified(obj, include_collections=False):
            continue
            
        before_vals = {}
        after_vals = {}
        has_changes = False
        
        for c in obj.__table__.columns:
            history = get_history(obj, c.key)
            if history.has_changes():
                has_changes = True
                
                old_val = history.deleted[0] if history.deleted else None
                new_val = history.added[0] if history.added else getattr(obj, c.key, None)
                
                # Format
                if old_val is not None and not isinstance(old_val, (int, float, str, bool, list, dict)):
                    if hasattr(old_val, 'value'):
                        old_val = old_val.value
                    else:
                        old_val = str(old_val)
                if new_val is not None and not isinstance(new_val, (int, float, str, bool, list, dict)):
                    if hasattr(new_val, 'value'):
                        new_val = new_val.value
                    else:
                        new_val = str(new_val)
                        
                before_vals[c.key] = old_val
                after_vals[c.key] = new_val
                
        if has_changes:
            event_record = AuditEvent(
                action="UPDATE",
                entity_name=type(obj).__name__,
                entity_id=str(getattr(obj, "id", "")),
                before_values=before_vals,
                after_values=after_vals,
                user_id=user_id,
                correlation_id=correlation_id
            )
            new_audit_events.append(event_record)

    # Process Deletes
    for obj in session.deleted:
        if not getattr(type(obj), "__audit__", False):
            continue
            
        before_vals = _get_model_dict(obj, is_deleted=True)
        event_record = AuditEvent(
            action="DELETE",
            entity_name=type(obj).__name__,
            entity_id=str(getattr(obj, "id", "")),
            before_values=before_vals,
            after_values=None,
            user_id=user_id,
            correlation_id=correlation_id
        )
        new_audit_events.append(event_record)

    # Add all audit records to the session.
    # We do this after iterating to prevent mutating session state while iterating.
    if new_audit_events:
        session.add_all(new_audit_events)
