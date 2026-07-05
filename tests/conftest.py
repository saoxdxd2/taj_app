import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.base import BaseModel

@pytest.fixture(scope="function")
def session():
    """
    Creates an in-memory SQLite session for testing.
    """
    engine = create_engine("sqlite:///:memory:")
    
    # Import all models to ensure metadata is populated
    from src.modules.authentication.models import User
    from src.modules.crm.models import Customer, Address
    from src.modules.suppliers.models import Supplier
    from src.modules.inventory.models import Product, Brand, Category, StockLevel, StockMovement
    from src.modules.purchasing.models import Purchase, PurchaseItem
    from src.modules.sales.models import Invoice, InvoiceItem, Quotation, QuotationItem
    from src.modules.finance.models import FinancialJournalEntry, Expense
    from src.modules.audit.models import AuditEvent
    import src.database.audit_listener
    from src.core.session import CurrentSession
    from src.core.context import RequestContext
    
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
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.rollback()
    session.close()
