"""Database connection and session management with thread safety."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from typing import Generator
import threading
from src.core.config import settings


# Thread-local storage for SQLite connections
_local = threading.local()


def get_engine():
    """Get thread-safe database engine."""
    if not hasattr(_local, 'engine'):
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            _local.engine = create_engine(
                settings.database_url,
                connect_args=connect_args,
                poolclass=StaticPool,
                echo=(settings.environment == "development")
            )
            
            # Enable foreign keys for SQLite
            @event.listens_for(_local.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        else:
            _local.engine = create_engine(
                settings.database_url,
                echo=(settings.environment == "development")
            )
    
    return _local.engine


def get_session_local() -> scoped_session:
    """Get thread-local database session."""
    engine = get_engine()
    return scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def get_db() -> Generator:
    """Dependency for FastAPI to get database session."""
    db = get_session_local()
    try:
        yield db
    finally:
        db.remove()


def init_db():
    """Initialize database tables."""
    from src.database.base import BaseModel
    # Import all models to ensure they're registered with the metadata
    from src.modules.inventory.models import Product, Brand, Category, StockLevel  # type: ignore
    from src.modules.sales.models import Invoice, InvoiceItem, Customer  # type: ignore
    from src.modules.purchasing.models import Purchase, PurchaseItem  # type: ignore
    from src.modules.audit.models import AuditEvent  # type: ignore
    from src.modules.suppliers.models import Supplier  # type: ignore
    
    engine = get_engine()
    BaseModel.metadata.create_all(bind=engine)
