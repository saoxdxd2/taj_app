"""
TAJ FROID ERP - Database Configuration
Async SQLAlchemy setup with connection pooling
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from typing import AsyncGenerator, Generator

from src.api.core.settings import settings


# Async engine for API endpoints
async_engine = create_async_engine(
    settings.database.effective_database_url,
    echo=settings.database.echo_sql,
    connect_args={"check_same_thread": False}
)

# Base class for models
Base = declarative_base()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for async database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Async session factory (defined after engine)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_db():
    """Initialize database tables"""
    async with async_engine.begin() as conn:
        # Import all models to register them with Base
        from src.modules.sales.models import Invoice, InvoiceItem, Quotation, Payment
        from src.modules.crm.models import Customer
        from src.modules.inventory.models import Product, StockMovement
        from src.modules.purchasing.models import PurchaseOrder, PurchaseItem
        from src.modules.suppliers.models import Supplier
        from src.modules.authentication.models import User, Role
        
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await async_engine.dispose()
