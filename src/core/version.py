# Application Version Information

APP_NAME = "TAJ FROID ERP"
APP_VERSION = "1.0.0-rc1"
BUILD_NUMBER = "20260705.1"
RELEASE_DATE = "2026-07-05"

def get_database_revision() -> str:
    """
    Retrieves the current alembic database revision.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine
    from src.core.paths import DB_PATH
    import os

    try:
        if not os.path.exists(DB_PATH):
            return "No Database"
            
        engine = create_engine(f"sqlite:///{DB_PATH}")
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            return current_rev or "None"
    except Exception:
        return "Unknown"
