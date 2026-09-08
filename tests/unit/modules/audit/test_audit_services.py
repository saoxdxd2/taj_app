"""
Tests for AuditService covering immutable audit logging.
"""
import pytest
from src.modules.audit.services import AuditService
from src.modules.audit.models import AuditEvent


class TestAuditService:
    """Test suite for AuditService business logic."""

    def test_record_event_success(self, session):
        """Test recording a basic audit event."""
        event = AuditService.record_event(
            session=session,
            action="CREATE_USER",
            entity_name="User",
            entity_id="123",
            before_values=None,
            after_values={"username": "testuser", "role": "Manager"},
            user_id=1,
            correlation_id="corr-123"
        )

        assert event is not None
        assert event.action == "CREATE_USER"
        assert event.entity_name == "User"
        assert event.entity_id == "123"
        assert event.after_values == {"username": "testuser", "role": "Manager"}
        assert event.user_id == 1
        assert event.correlation_id == "corr-123"
        assert event.timestamp is not None

    def test_record_event_minimal_fields(self, session):
        """Test recording an audit event with only required fields."""
        event = AuditService.record_event(
            session=session,
            action="VIEW_REPORT",
            entity_name="Report"
        )

        assert event is not None
        assert event.action == "VIEW_REPORT"
        assert event.entity_name == "Report"
        assert event.entity_id is None
        assert event.before_values is None
        assert event.after_values is None
        assert event.user_id is None
        assert event.correlation_id is None

    def test_record_event_missing_action_fails(self, session):
        """Test that recording an event without action fails."""
        with pytest.raises(ValueError, match="Action and entity_name are mandatory"):
            AuditService.record_event(
                session=session,
                action="",
                entity_name="User"
            )

    def test_record_event_missing_entity_name_fails(self, session):
        """Test that recording an event without entity_name fails."""
        with pytest.raises(ValueError, match="Action and entity_name are mandatory"):
            AuditService.record_event(
                session=session,
                action="DELETE",
                entity_name=""
            )

    def test_record_event_with_before_and_after_values(self, session):
        """Test recording an update event with before and after values."""
        event = AuditService.record_event(
            session=session,
            action="UPDATE_PRODUCT_PRICE",
            entity_name="Product",
            entity_id="456",
            before_values={"price": 10.00, "stock": 100},
            after_values={"price": 15.00, "stock": 95},
            user_id=2
        )

        assert event is not None
        assert event.before_values == {"price": 10.00, "stock": 100}
        assert event.after_values == {"price": 15.00, "stock": 95}

    def test_record_event_complex_data_types(self, session):
        """Test recording an event with complex data types in values."""
        from decimal import Decimal
        from datetime import datetime

        event = AuditService.record_event(
            session=session,
            action="VALIDATE_INVOICE",
            entity_name="Invoice",
            entity_id="INV-2024-001",
            before_values={"status": "draft"},
            after_values={
                "status": "validated",
                "total_amount": Decimal("1250.50"),
                "validated_at": datetime.now().isoformat(),
                "items_count": 5
            },
            user_id=3,
            correlation_id="inv-corr-001"
        )

        assert event is not None
        assert event.after_values["total_amount"] == Decimal("1250.50")
        assert event.after_values["items_count"] == 5

    def test_record_multiple_events_preserves_order(self, session):
        """Test that multiple events are recorded in order."""
        events = []
        for i in range(5):
            event = AuditService.record_event(
                session=session,
                action=f"ACTION_{i}",
                entity_name="TestEntity",
                entity_id=str(i),
                user_id=i
            )
            events.append(event)

        # Retrieve all events
        all_events = session.query(AuditEvent).order_by(AuditEvent.id).all()
        
        assert len(all_events) == 5
        for i, event in enumerate(all_events):
            assert event.action == f"ACTION_{i}"
            assert event.entity_id == str(i)

    def test_record_event_null_user_id_allowed(self, session):
        """Test recording an event with null user_id (system action)."""
        event = AuditService.record_event(
            session=session,
            action="SYSTEM_BACKUP",
            entity_name="Database",
            user_id=None
        )

        assert event is not None
        assert event.user_id is None
        assert event.action == "SYSTEM_BACKUP"

    def test_record_event_null_correlation_id_allowed(self, session):
        """Test recording an event without correlation_id."""
        event = AuditService.record_event(
            session=session,
            action="STANDALONE_ACTION",
            entity_name="System",
            correlation_id=None
        )

        assert event is not None
        assert event.correlation_id is None

    def test_record_delete_event(self, session):
        """Test recording a delete/soft-delete event."""
        event = AuditService.record_event(
            session=session,
            action="SOFT_DELETE",
            entity_name="Customer",
            entity_id="789",
            before_values={"is_active": True, "name": "John Doe"},
            after_values={"is_active": False, "deleted_at": "2024-01-15T10:30:00Z"},
            user_id=4
        )

        assert event is not None
        assert event.action == "SOFT_DELETE"
        assert event.before_values["is_active"] is True
        assert event.after_values["is_active"] is False

    def test_record_event_large_payload(self, session):
        """Test recording an event with large before/after values."""
        large_dict = {f"key_{i}": f"value_{i}" for i in range(50)}
        
        event = AuditService.record_event(
            session=session,
            action="BULK_UPDATE",
            entity_name="Inventory",
            entity_id="BATCH-001",
            before_values=large_dict,
            after_values=large_dict,
            user_id=5
        )

        assert event is not None
        assert len(event.before_values) == 50
        assert len(event.after_values) == 50

    def test_record_event_special_characters_in_values(self, session):
        """Test recording an event with special characters in values."""
        event = AuditService.record_event(
            session=session,
            action="UPDATE_DESCRIPTION",
            entity_name="Product",
            entity_id="SPEC-001",
            before_values={"description": "Normal text"},
            after_values={
                "description": "Text with special chars: <>&\"' and unicode: ñ é ü 中文"
            },
            user_id=6
        )

        assert event is not None
        assert "ñ é ü 中文" in event.after_values["description"]

    def test_audit_event_immutable_after_creation(self, session):
        """Test that audit events cannot be modified (conceptual test)."""
        # Record an event
        event = AuditService.record_event(
            session=session,
            action="INITIAL_STATE",
            entity_name="Test",
            entity_id="IMMUTABLE-001",
            after_values={"value": "original"},
            user_id=7
        )

        original_timestamp = event.timestamp
        original_action = event.action
        
        # The service doesn't provide update/delete methods by design
        # This test documents the immutability guarantee
        assert event.action == "INITIAL_STATE"
        assert original_timestamp is not None
        
        # Verify no update method exists on the service
        assert not hasattr(AuditService, 'update_event')
        assert not hasattr(AuditService, 'delete_event')
