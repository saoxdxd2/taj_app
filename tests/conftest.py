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
    
    BaseModel.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.rollback()
    session.close()
    BaseModel.metadata.drop_all(engine)
