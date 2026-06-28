# backend/alembic/env.py
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

load_dotenv()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override URL from environment so .env is the single source of truth
db_url = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

import sys
# Import all models so Alembic can detect schema changes
try:
    import app.models  # noqa: F401 — registers all models with Base
    from app.database import Base
except Exception as _e:
    print(f"ALEMBIC IMPORT ERROR: {_e}", file=sys.stderr, flush=True)
    raise

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine, text
    url = db_url or config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # Fail fast if metadata lock blocks DDL — prevents Railway deploy hang
        connection.execute(text("SET SESSION lock_wait_timeout = 30"))
        connection.execute(text("SET SESSION innodb_lock_wait_timeout = 30"))
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
