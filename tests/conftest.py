import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from src.database.base import BaseModel
from src.core.context import RequestContext

@pytest.fixture(scope="function")
def db_engine():
    """
    Creates an in-memory SQLite engine with migrations applied.
    """
    engine = create_engine("sqlite:///:memory:")

    # Enforce foreign keys on this engine (each engine registers its own pragmas)
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    # Import all models to ensure metadata is populated
    from src.modules.authentication.models import User
    from src.modules.crm.models import Customer, Address
    from src.modules.suppliers.models import Supplier
    from src.modules.inventory.models import Product, Brand, Category, StockLevel, StockMovement
    from src.modules.purchasing.models import Purchase, PurchaseItem
    from src.modules.sales.models import (
        Invoice, InvoiceItem, Quotation, QuotationItem,
        Payment, CustomerDeposit, SalesReturn, ReturnItem,
    )
    from src.modules.finance.models import FinancialJournalEntry, Expense, Check
    from src.modules.inventory.models import AttributeDef, ProductAttribute
    from src.modules.audit.models import AuditEvent
    from src.modules.pricing.models import PricingPolicy
    import src.database.audit_listener
    from src.core.session import CurrentSession
    
    # Initialize CurrentSession so audit listeners don't fail
    CurrentSession.initialize(RequestContext(user_id="1", username="admin", role="Administrator", permissions=set()))
    
    from alembic.config import Config
    from alembic import command
    import os
    
    # Run Alembic migrations on the test memory database
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_ini_path = os.path.join(project_root, "alembic.ini")
    alembic_cfg = Config(alembic_ini_path)
    # We must use the same engine for Alembic
    with engine.begin() as connection:
        alembic_cfg.attributes['connection'] = connection
        command.upgrade(alembic_cfg, "head")
    
    return engine


@pytest.fixture(scope="function")
def session(db_engine):
    """
    Creates an in-memory SQLite session for testing.
    """
    Session = sessionmaker(bind=db_engine)
    session = Session()

    yield session

    session.rollback()
    session.close()


# ----------------------------------------------------------------------
# Shared request contexts
# ----------------------------------------------------------------------
# These were previously redefined in every test module. They are
# identical everywhere, so they live here to be defined exactly once.

@pytest.fixture
def admin_context():
    """A context with full access, for the common 'allowed' case."""
    return RequestContext(
        user_id="1", username="admin", role="Administrator",
        permissions={"Everything"},
    )


@pytest.fixture
def unauthorized_context():
    """A context with no permissions, for asserting AccessDenied."""
    return RequestContext(
        user_id="2", username="guest", role="Guest", permissions=set(),
    )


@pytest.fixture
def cashier_context():
    """A context limited to sales, for permission-scope tests."""
    return RequestContext(
        user_id="3", username="cashier", role="Cashier",
        permissions={"Sales.*"},
    )
