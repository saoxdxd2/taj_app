from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Do not call logging.config.fileConfig here. The application installs a
# loguru file sink plus a stdlib bridge in src.core.logging; fileConfig
# would replace the root handler with Alembic's console handler and
# disable existing loggers, so service/UI errors would stop reaching the
# rotating log file. Alembic's own log records use the root configuration
# installed by the application (or Python's last-resort handler when the
# migrations are run standalone).

# add your model's MetaData object here
# for 'autogenerate' support
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.database.base import BaseModel
import src.modules.inventory.models
import src.modules.crm.models
import src.modules.suppliers.models
import src.modules.purchasing.models
import src.modules.sales.models
import src.modules.finance.models
import src.modules.audit.models
import src.modules.authentication.models

target_metadata = BaseModel.metadata

# Override URL from our app configuration
from src.database.session import DB_PATH
config.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    import sqlalchemy as sa
    connectable = config.attributes.get('connection', None)

    if connectable is None:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    if isinstance(connectable, sa.engine.Connection):
        context.configure(
            connection=connectable, 
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        with connectable.connect() as connection:
            context.configure(
                connection=connection, 
                target_metadata=target_metadata,
                render_as_batch=True,
            )

            with context.begin_transaction():
                context.run_migrations()




if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
