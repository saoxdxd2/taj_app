"""
Tests for PurchasingService covering purchase order lifecycle.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from src.modules.purchasing.services import PurchasingService
from src.modules.purchasing.models import Purchase, PurchaseItem, PurchaseState
from src.core.context import RequestContext


class TestPurchasingService:
    """Test suite for PurchasingService business logic."""

    @pytest.fixture
    def admin_context(self):
        """Create an admin user context with purchasing permissions."""
        return RequestContext(
            user_id="1",
            username="admin",
            role="Administrator",
            permissions={
                "Purchasing.Purchases.View",
                "Purchasing.Purchases.Create",
                "Purchasing.Purchases.Update",
                "Purchasing.Purchases.Validate",
                "Inventory.Stock.Update",
                "Finance.JournalEntries.Create",
            },
            correlation_id="test-correlation",
            workstation="test-workstation",
            language="en",
            timestamp=datetime.now()
        )

    @pytest.fixture
    def sample_supplier(self, session):
        """Create a test supplier."""
        from src.modules.suppliers.models import Supplier
        supplier = Supplier(
            company_name="Test Supplier Co.",
            contact_name="John Doe",
            email="contact@testsupplier.com",
            phone="+1234567890"
        )
        session.add(supplier)
        session.flush()
        return supplier

    @pytest.fixture
    def sample_product(self, session):
        """Create a test product."""
        from src.modules.inventory.models import Product, Category, Brand, ProductType
        category = Category(name="Test Category")
        brand = Brand(name="Test Brand")
        session.add_all([category, brand])
        session.flush()
        
        product = Product(
            name="Test Product",
            sku="TEST-001",
            category_id=category.id,
            brand_id=brand.id,
            purchase_price=Decimal("10.00"),
            sale_price=Decimal("15.00"),
            product_type=ProductType.PHYSICAL
        )
        session.add(product)
        session.flush()
        return product

    def test_get_all_purchases_empty(self, session, admin_context):
        """Test retrieving purchases when none exist."""
        purchases = PurchasingService.get_all_purchases(
            context=admin_context, session=session, limit=10, offset=0
        )
        assert purchases == []

    def test_count_all_purchases_empty(self, session, admin_context):
        """Test counting purchases when none exist."""
        count = PurchasingService.count_all_purchases(context=admin_context, session=session)
        assert count == 0

    def test_create_purchase_draft_success(self, session, admin_context, sample_supplier):
        """Test creating a new draft purchase order."""
        reference = "PO-2024-001"
        
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context,
            session=session,
            reference=reference,
            supplier_id=sample_supplier.id
        )
        
        assert purchase is not None
        assert purchase.reference == reference
        assert purchase.supplier_id == sample_supplier.id
        assert purchase.state == PurchaseState.DRAFT
        assert purchase.total_amount == Decimal("0.00")
        assert purchase.items == []

    def test_create_purchase_draft_missing_reference(self, session, admin_context, sample_supplier):
        """Test that creating a draft without reference raises error."""
        with pytest.raises(ValueError, match="Purchase reference is required"):
            PurchasingService.create_purchase_draft(
                context=admin_context,
                session=session,
                reference="",
                supplier_id=sample_supplier.id
            )

    def test_get_purchase_with_items(self, session, admin_context, sample_supplier, sample_product):
        """Test retrieving a purchase with its items loaded."""
        # Create a purchase
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-002", supplier_id=sample_supplier.id
        )
        
        # Add an item
        PurchasingService.add_item_to_purchase(
            context=admin_context, session=session,
            purchase_id=purchase.id,
            product_id=sample_product.id,
            quantity=10,
            unit_cost=Decimal("10.00")
        )
        session.flush()
        
        # Retrieve with items
        retrieved = PurchasingService.get_purchase_with_items(
            context=admin_context, purchase_id=purchase.id, session=session
        )
        
        assert retrieved is not None
        assert len(retrieved.items) == 1
        assert retrieved.items[0].quantity == 10
        assert retrieved.items[0].unit_cost == Decimal("10.00")

    def test_add_item_to_draft_purchase(self, session, admin_context, sample_supplier, sample_product):
        """Test adding an item to a draft purchase."""
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-003", supplier_id=sample_supplier.id
        )
        
        item = PurchasingService.add_item_to_purchase(
            context=admin_context, session=session,
            purchase_id=purchase.id,
            product_id=sample_product.id,
            quantity=5,
            unit_cost=Decimal("12.50")
        )
        
        assert item is not None
        assert item.product_id == sample_product.id
        assert item.quantity == 5
        assert item.unit_cost == Decimal("12.50")
        
        # Verify total was updated
        session.refresh(purchase)
        assert purchase.total_amount == Decimal("62.50")  # 5 * 12.50

    def test_add_multiple_items_updates_total(self, session, admin_context, sample_supplier, sample_product):
        """Test that adding multiple items correctly updates the total."""
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-004", supplier_id=sample_supplier.id
        )
        
        # Add first item
        PurchasingService.add_item_to_purchase(
            context=admin_context, session=session,
            purchase_id=purchase.id,
            product_id=sample_product.id,
            quantity=10,
            unit_cost=Decimal("10.00")
        )
        
        # Add second item
        PurchasingService.add_item_to_purchase(
            context=admin_context, session=session,
            purchase_id=purchase.id,
            product_id=sample_product.id,
            quantity=5,
            unit_cost=Decimal("20.00")
        )
        
        session.refresh(purchase)
        assert purchase.total_amount == Decimal("200.00")  # (10*10) + (5*20)

    def test_add_item_to_non_draft_purchase_fails(self, session, admin_context, sample_supplier, sample_product):
        """Test that adding items to a non-draft purchase fails."""
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-005", supplier_id=sample_supplier.id
        )
        
        # Validate the purchase to change state
        PurchasingService.add_item_to_purchase(
            context=admin_context, session=session,
            purchase_id=purchase.id,
            product_id=sample_product.id,
            quantity=1,
            unit_cost=Decimal("10.00")
        )
        
        # Manually change state to validated (bypassing service for this test)
        purchase.state = PurchaseState.VALIDATED
        session.flush()
        
        with pytest.raises(ValueError, match="Cannot add items to a purchase that is not in Draft state"):
            PurchasingService.add_item_to_purchase(
                context=admin_context, session=session,
                purchase_id=purchase.id,
                product_id=sample_product.id,
                quantity=5,
                unit_cost=Decimal("10.00")
            )

    def test_add_item_with_zero_quantity_fails(self, session, admin_context, sample_supplier, sample_product):
        """Test that adding an item with zero quantity fails."""
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-006", supplier_id=sample_supplier.id
        )
        
        with pytest.raises(ValueError, match="Quantity must be greater than zero"):
            PurchasingService.add_item_to_purchase(
                context=admin_context, session=session,
                purchase_id=purchase.id,
                product_id=sample_product.id,
                quantity=0,
                unit_cost=Decimal("10.00")
            )

    def test_add_item_with_negative_cost_fails(self, session, admin_context, sample_supplier, sample_product):
        """Test that adding an item with negative cost fails."""
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-007", supplier_id=sample_supplier.id
        )
        
        with pytest.raises(ValueError, match="Unit cost cannot be negative"):
            PurchasingService.add_item_to_purchase(
                context=admin_context, session=session,
                purchase_id=purchase.id,
                product_id=sample_product.id,
                quantity=5,
                unit_cost=Decimal("-10.00")
            )

    def test_validate_purchase_success(self, session, admin_context, sample_supplier, sample_product):
        """Test successfully validating a purchase order."""
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-008", supplier_id=sample_supplier.id
        )
        
        PurchasingService.add_item_to_purchase(
            context=admin_context, session=session,
            purchase_id=purchase.id,
            product_id=sample_product.id,
            quantity=10,
            unit_cost=Decimal("15.00")
        )
        
        result = PurchasingService.validate_purchase(
            context=admin_context, session=session, purchase_id=purchase.id
        )
        
        assert result is True
        session.refresh(purchase)
        assert purchase.state == PurchaseState.VALIDATED

    def test_validate_purchase_with_no_items_fails(self, session, admin_context, sample_supplier):
        """Test that validating a purchase with no items fails."""
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-009", supplier_id=sample_supplier.id
        )
        
        with pytest.raises(ValueError, match="Cannot validate a purchase with no items"):
            PurchasingService.validate_purchase(
                context=admin_context, session=session, purchase_id=purchase.id
            )

    def test_validate_nonexistent_purchase_returns_false(self, session, admin_context):
        """Test that validating a non-existent purchase returns False."""
        result = PurchasingService.validate_purchase(
            context=admin_context, session=session, purchase_id=99999
        )
        assert result is False

    def test_get_product_cost_history(self, session, admin_context, sample_supplier, sample_product):
        """Test retrieving cost history for a product."""
        # Create and validate two purchases
        for i in range(2):
            purchase = PurchasingService.create_purchase_draft(
                context=admin_context, session=session,
                reference=f"PO-2024-0{i+1}0", supplier_id=sample_supplier.id
            )
            PurchasingService.add_item_to_purchase(
                context=admin_context, session=session,
                purchase_id=purchase.id,
                product_id=sample_product.id,
                quantity=10,
                unit_cost=Decimal(f"{10.00 + i}")
            )
            PurchasingService.validate_purchase(
                context=admin_context, session=session, purchase_id=purchase.id
            )
        
        history = PurchasingService.get_product_cost_history(
            context=admin_context, session=session, product_id=sample_product.id, limit=10
        )
        
        assert len(history) == 2
        # Most recent first
        assert history[0]["unit_cost"] == Decimal("11.00")
        assert history[1]["unit_cost"] == Decimal("10.00")

    def test_get_last_purchase_cost(self, session, admin_context, sample_supplier, sample_product):
        """Test retrieving the last purchase cost for a product."""
        # No purchases yet
        cost = PurchasingService.get_last_purchase_cost(
            context=admin_context, session=session, product_id=sample_product.id
        )
        assert cost is None
        
        # Create and validate a purchase
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-011", supplier_id=sample_supplier.id
        )
        PurchasingService.add_item_to_purchase(
            context=admin_context, session=session,
            purchase_id=purchase.id,
            product_id=sample_product.id,
            quantity=5,
            unit_cost=Decimal("25.00")
        )
        PurchasingService.validate_purchase(
            context=admin_context, session=session, purchase_id=purchase.id
        )
        
        cost = PurchasingService.get_last_purchase_cost(
            context=admin_context, session=session, product_id=sample_product.id
        )
        assert cost == Decimal("25.00")

    def test_get_product_cost_history_excludes_drafts(self, session, admin_context, sample_supplier, sample_product):
        """Test that cost history only includes validated purchases."""
        # Create a draft purchase (not validated)
        purchase = PurchasingService.create_purchase_draft(
            context=admin_context, session=session,
            reference="PO-2024-012", supplier_id=sample_supplier.id
        )
        PurchasingService.add_item_to_purchase(
            context=admin_context, session=session,
            purchase_id=purchase.id,
            product_id=sample_product.id,
            quantity=10,
            unit_cost=Decimal("30.00")
        )
        # Don't validate - leave as draft
        
        history = PurchasingService.get_product_cost_history(
            context=admin_context, session=session, product_id=sample_product.id, limit=10
        )
        
        # Should be empty since the purchase is still a draft
        assert len(history) == 0
