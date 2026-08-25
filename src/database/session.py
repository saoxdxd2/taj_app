from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.core.paths import DB_PATH

DATABASE_URL = f"sqlite:///{DB_PATH}"

# Engine with SQLite specific foreign key constraint enforcement
engine = create_engine(
    DATABASE_URL, 
    echo=False, 
    connect_args={"check_same_thread": False}
)

# Enforce foreign keys for SQLite.
# NOTE: registered on THIS engine instance only — not the global Engine
# class — so test engines and other engines in the process are unaffected
# and must register their own pragmas.
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# Register the audit listener
import src.database.audit_listener

def get_session():
    """Dependency to provide a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
