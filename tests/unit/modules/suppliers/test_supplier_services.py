"""
Tests for SupplierService covering supplier management.
"""
import pytest
from src.modules.suppliers.services import SupplierService
from src.modules.suppliers.models import Supplier
from src.core.context import RequestContext
from datetime import datetime


class TestSupplierService:
    """Test suite for SupplierService business logic."""

    @pytest.fixture
    def admin_context(self):
        """Create an admin user context with supplier permissions."""
        return RequestContext(
            user_id="1",
            username="admin",
            role="Administrator",
            permissions={
                "Suppliers.Suppliers.View",
                "Suppliers.Suppliers.Create",
                "Suppliers.Suppliers.Update",
                "Suppliers.Suppliers.Archive",
            },
            correlation_id="test-correlation",
            workstation="test-workstation",
            language="en",
            timestamp=datetime.now()
        )

    def test_get_all_suppliers_empty(self, session, admin_context):
        """Test retrieving suppliers when none exist."""
        suppliers = SupplierService.get_all_suppliers(
            context=admin_context, session=session, limit=10, offset=0
        )
        assert suppliers == []

    def test_count_all_suppliers_empty(self, session, admin_context):
        """Test counting suppliers when none exist."""
        count = SupplierService.count_all_suppliers(context=admin_context, session=session)
        assert count == 0

    def test_create_supplier_success(self, session, admin_context):
        """Test creating a new supplier with all fields."""
        company_name = "Test Supplier Co."
        contact_name = "John Doe"
        email = "contact@testsupplier.com"
        phone = "+1234567890"
        ice_number = "ICE123456789"

        supplier = SupplierService.create_supplier(
            context=admin_context,
            session=session,
            company_name=company_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            ice_number=ice_number
        )

        assert supplier is not None
        assert supplier.company_name == company_name
        assert supplier.contact_name == contact_name
        assert supplier.email == email
        assert supplier.phone == phone
        assert supplier.ice_number == ice_number
        assert supplier.is_archived is False

    def test_create_supplier_minimal_fields(self, session, admin_context):
        """Test creating a supplier with only required fields."""
        company_name = "Minimal Supplier"

        supplier = SupplierService.create_supplier(
            context=admin_context,
            session=session,
            company_name=company_name
        )

        assert supplier is not None
        assert supplier.company_name == company_name
        assert supplier.contact_name is None
        assert supplier.email is None
        assert supplier.phone is None
        assert supplier.ice_number is None

    def test_create_supplier_missing_company_name(self, session, admin_context):
        """Test that creating a supplier without company name fails."""
        with pytest.raises(ValueError, match="Company name is required"):
            SupplierService.create_supplier(
                context=admin_context,
                session=session,
                company_name=""
            )

    def test_get_supplier_by_id(self, session, admin_context):
        """Test retrieving a supplier by ID."""
        # Create a supplier
        created = SupplierService.create_supplier(
            context=admin_context,
            session=session,
            company_name="Retrieve Test Supplier"
        )

        # Retrieve it
        retrieved = SupplierService.get_supplier_by_id(
            context=admin_context,
            supplier_id=created.id,
            session=session
        )

        assert retrieved is not None
        assert retrieved.company_name == "Retrieve Test Supplier"
        assert retrieved.id == created.id

    def test_get_nonexistent_supplier_returns_none(self, session, admin_context):
        """Test retrieving a non-existent supplier returns None."""
        result = SupplierService.get_supplier_by_id(
            context=admin_context,
            supplier_id=99999,
            session=session
        )
        assert result is None

    def test_update_supplier_success(self, session, admin_context):
        """Test updating a supplier's information."""
        # Create a supplier
        created = SupplierService.create_supplier(
            context=admin_context,
            session=session,
            company_name="Original Company",
            contact_name="Original Contact",
            email="original@example.com"
        )

        # Update it
        updated = SupplierService.update_supplier(
            context=admin_context,
            session=session,
            supplier_id=created.id,
            company_name="Updated Company Name",
            contact_name="Updated Contact",
            email="updated@example.com",
            phone="+9876543210",
            ice_number="NEW123456"
        )

        assert updated is not None
        assert updated.company_name == "Updated Company Name"
        assert updated.contact_name == "Updated Contact"
        assert updated.email == "updated@example.com"
        assert updated.phone == "+9876543210"
        assert updated.ice_number == "NEW123456"

    def test_update_supplier_missing_company_name(self, session, admin_context):
        """Test that updating a supplier without company name fails."""
        created = SupplierService.create_supplier(
            context=admin_context,
            session=session,
            company_name="Test Company"
        )

        with pytest.raises(ValueError, match="Company name is required"):
            SupplierService.update_supplier(
                context=admin_context,
                session=session,
                supplier_id=created.id,
                company_name=""
            )

    def test_update_nonexistent_supplier_returns_none(self, session, admin_context):
        """Test updating a non-existent supplier returns None."""
        result = SupplierService.update_supplier(
            context=admin_context,
            session=session,
            supplier_id=99999,
            company_name="Test Company"
        )
        assert result is None

    def test_archive_supplier_success(self, session, admin_context):
        """Test archiving (soft deleting) a supplier."""
        created = SupplierService.create_supplier(
            context=admin_context,
            session=session,
            company_name="To Archive Supplier"
        )

        result = SupplierService.archive_supplier(
            context=admin_context,
            session=session,
            supplier_id=created.id
        )

        assert result is True
        session.refresh(created)
        assert created.is_archived is True

    def test_archive_nonexistent_supplier_returns_false(self, session, admin_context):
        """Test archiving a non-existent supplier returns False."""
        result = SupplierService.archive_supplier(
            context=admin_context,
            session=session,
            supplier_id=99999
        )
        assert result is False

    def test_get_all_suppliers_pagination(self, session, admin_context):
        """Test pagination of suppliers list."""
        # Create multiple suppliers
        for i in range(15):
            SupplierService.create_supplier(
                context=admin_context,
                session=session,
                company_name=f"Supplier {i}"
            )

        # Get first page
        first_page = SupplierService.get_all_suppliers(
            context=admin_context, session=session, limit=10, offset=0
        )
        assert len(first_page) == 10

        # Get second page
        second_page = SupplierService.get_all_suppliers(
            context=admin_context, session=session, limit=10, offset=10
        )
        assert len(second_page) == 5

    def test_count_all_suppliers_after_creation(self, session, admin_context):
        """Test counting suppliers after creating some."""
        # Create 5 suppliers
        for i in range(5):
            SupplierService.create_supplier(
                context=admin_context,
                session=session,
                company_name=f"Count Test Supplier {i}"
            )

        count = SupplierService.count_all_suppliers(context=admin_context, session=session)
        assert count == 5

    def test_update_supplier_partial_fields(self, session, admin_context):
        """Test updating only some fields of a supplier."""
        created = SupplierService.create_supplier(
            context=admin_context,
            session=session,
            company_name="Partial Update Supplier",
            contact_name="Original Contact",
            email="original@example.com"
        )

        # Update only email and phone
        updated = SupplierService.update_supplier(
            context=admin_context,
            session=session,
            supplier_id=created.id,
            company_name="Partial Update Supplier",  # Required field must be provided
            email="newemail@example.com",
            phone="+1111111111"
        )

        assert updated.email == "newemail@example.com"
        assert updated.phone == "+1111111111"
        # Contact name should remain unchanged
        assert updated.contact_name == "Original Contact"
