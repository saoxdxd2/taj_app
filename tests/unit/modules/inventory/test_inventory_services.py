import pytest
import time
from decimal import Decimal
from src.modules.inventory.services import InventoryService
from src.modules.inventory.models import Product, ProductState, ProductType, StockLevel, StockMovement
from src.modules.audit.models import AuditEvent
from src.core.context import RequestContext
from src.security.permissions import AccessDenied

# --- Fixtures ---

@pytest.fixture
def admin_context():
    return RequestContext(user_id="1", username="admin", role="Administrator", permissions={"Everything"})

@pytest.fixture
def unauthorized_context():
    return RequestContext(user_id="2", username="guest", role="Guest", permissions=set())

# --- Authorization Tests ---

def test_authorization_success(session, admin_context):
    """Test that authorized users can create products."""
    product = InventoryService.create_product(
        context=admin_context, session=session, 
        name="Auth Test", sku="AUTH-01", purchase_price=Decimal("10.00"), sale_price=Decimal("20.00")
    )
    assert product.id is not None

def test_authorization_failure(session, unauthorized_context):
    """Test that unauthorized users are blocked from creating products."""
    with pytest.raises(AccessDenied):
        InventoryService.create_product(
            context=unauthorized_context, session=session, 
            name="Auth Fail", sku="FAIL-01", purchase_price=Decimal("10.00"), sale_price=Decimal("20.00")
        )

# --- Validation Tests ---

def test_validation_negative_price(session, admin_context):
    """Test that negative prices trigger ValueError validation."""
    with pytest.raises(ValueError, match="Prices cannot be negative"):
        InventoryService.create_product(
            context=admin_context, session=session, 
            name="Neg Price", sku="NEG-01", purchase_price=Decimal("-10.00"), sale_price=Decimal("20.00")
        )

# --- CRUD Tests ---

def test_crud_lifecycle(session, admin_context):
    """Test the full lifecycle: Create, Update, Activate, Archive."""
    # 1. Create
    product = InventoryService.create_product(
        context=admin_context, session=session, 
        name="Lifecycle", sku="LIFE-01", purchase_price=Decimal("10.00"), sale_price=Decimal("20.00")
    )
    product_id = product.id
    
    # 2. Read / Verify state
    assert product.state == ProductState.DRAFT
    
    # 3. Update
    updated = InventoryService.update_product(
        context=admin_context, session=session, product_id=product_id,
        name="Lifecycle Updated", sku="LIFE-01", product_type=ProductType.PHYSICAL,
        purchase_price=Decimal("15.00"), sale_price=Decimal("25.00"), vat_rate=Decimal("20.00"),
        brand_id=None, category_id=None
    )
    assert updated.name == "Lifecycle Updated"
    
    # 4. Activate
    assert InventoryService.activate_product(admin_context, session, product_id) is True
    assert updated.state == ProductState.ACTIVE
    
    # 5. Archive
    assert InventoryService.archive_product(admin_context, session, product_id) is True
    assert updated.state == ProductState.ARCHIVED

# --- Transaction Rollback Tests ---

def test_transaction_rollback(session, admin_context):
    """Test that exceptions naturally bubble up so the caller can rollback."""
    # Create valid product
    product = InventoryService.create_product(
        context=admin_context, session=session, 
        name="Rollback", sku="RB-01", purchase_price=Decimal("10.00"), sale_price=Decimal("20.00")
    )
    session.commit()
    
    try:
        # Trigger validation error on update
        InventoryService.update_product(
            context=admin_context, session=session, product_id=product.id,
            name="Invalid Update", sku="RB-01", product_type=ProductType.PHYSICAL,
            purchase_price=Decimal("-100.00"), sale_price=Decimal("20.00"), vat_rate=Decimal("20.00"),
            brand_id=None, category_id=None
        )
        session.commit() # Should not reach here
    except ValueError:
        session.rollback()
        
    # Verify rollback
    db_product = session.query(Product).filter(Product.id == product.id).first()
    assert db_product.name == "Rollback" # Did not change

# --- Audit Tests ---

def test_audit_event_generation(session, admin_context):
    """Test that CRUD operations correctly generate immutable audit events."""
    # Clear audit table
    session.query(AuditEvent).delete()
    
    product = InventoryService.create_product(
        context=admin_context, session=session, 
        name="Audit Test", sku="AUD-01", purchase_price=Decimal("10.00"), sale_price=Decimal("20.00")
    )
    
    # Verify CREATE audit event
    events = session.query(AuditEvent).filter(AuditEvent.entity_name == "Product").all()
    assert len(events) == 1
    assert events[0].action == "CREATE"
    assert events[0].after_values["sku"] == "AUD-01"
    assert events[0].user_id == 1

    # Update product
    product = InventoryService.update_product(
        context=admin_context, session=session, product_id=product.id,
        name="Audit Test Updated", sku="AUD-02", purchase_price=Decimal("10.00"), sale_price=Decimal("20.00"),
        product_type=ProductType.PHYSICAL, vat_rate=Decimal("0.00"), brand_id=None, category_id=None
    )

    # Verify UPDATE audit event
    events = session.query(AuditEvent).filter(AuditEvent.entity_name == "Product").order_by(AuditEvent.id).all()
    assert len(events) == 2
    assert events[1].action == "UPDATE"
    assert events[1].before_values["sku"] == "AUD-01"
    assert events[1].after_values["sku"] == "AUD-02"

# --- Performance Smoke Test ---

def test_performance_smoke_test(session, admin_context):
    """Smoke test to ensure loading 100 products executes in O(n) under 100ms."""
    # Seed 100 products
    for i in range(100):
        InventoryService.create_product(
            context=admin_context, session=session, 
            name=f"Perf {i}", sku=f"PF-{i}", purchase_price=Decimal("1.00"), sale_price=Decimal("2.00")
        )
    session.commit()
    
    start = time.time()
    products = InventoryService.get_all_products(admin_context, session)
    duration = time.time() - start
    
    assert len(products) == 100
    assert duration < 0.1 # Must be faster than 100ms
