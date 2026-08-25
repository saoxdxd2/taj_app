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

# Per-connection SQLite tuning (registered on THIS engine instance only —
# not the global Engine class — so test engines are unaffected and must
# register their own pragmas).
#
# Speed & reliability:
#   - foreign_keys=ON     : enforce referential integrity
#   - journal_mode=WAL    : readers never block the writer; much faster commits
#   - synchronous=NORMAL  : safe with WAL, removes fsync-per-commit overhead
#   - temp_store=MEMORY   : temp tables/sorts in RAM instead of disk
#   - cache_size=-16000   : ~16 MB page cache (default is ~2 MB)
#   - busy_timeout=5000   : wait up to 5s on locks instead of failing instantly
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA cache_size=-16000")
    cursor.execute("PRAGMA busy_timeout=5000")
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
