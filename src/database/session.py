from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Define database path inside the 'data/' directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
# Ensure the data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "taj_app.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Engine with SQLite specific foreign key constraint enforcement
engine = create_engine(
    DATABASE_URL, 
    echo=False, 
    connect_args={"check_same_thread": False}
)

# Enforce foreign keys for SQLite
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    """Dependency to provide a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
