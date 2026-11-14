"""Database engine, session factory, and Base class."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import API_ROOT, settings

_is_sqlite = settings.database_url.startswith("sqlite")
# check_same_thread is a SQLite-only flag.
connect_args = {"check_same_thread": False} if _is_sqlite else {}

# pool_pre_ping: hosted Postgres (Neon) drops idle connections, so check each
# pooled connection before use instead of failing the first request after a lull.
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=not _is_sqlite,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

if _is_sqlite:
    # SQLite ignores ON DELETE CASCADE unless foreign keys are switched on per
    # connection. Deleting an upload or team relies on the cascade.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


class Base(DeclarativeBase):
    pass


class LegacyDatabaseError(RuntimeError):
    pass


def init_db() -> None:
    """Bring the database schema up to date (``alembic upgrade head``)."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from . import models  # noqa: F401  (register models on Base.metadata)

    tables = set(inspect(engine).get_table_names())
    if "plays" in tables and "alembic_version" not in tables:
        # Pre-migration database: its plays have no owning team, so they
        # can't be assigned safely. Refuse rather than guess.
        raise LegacyDatabaseError(
            "This database predates team-scoped plays and migrations "
            f"({settings.database_url}). Its plays have no owner and can't be "
            "migrated. Back it up and delete it (local dev: rm api/engage8.db), "
            "then start the API again and re-upload your CSVs."
        )

    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(API_ROOT) / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
