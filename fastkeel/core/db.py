# fastkeel/core/db.py
import sqlite3
from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, StaticPool, create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from fastkeel.core.config import Config

engine: Engine | None = None
SessionLocal: sessionmaker | None = None
Base = declarative_base()


def init_db(config: Config) -> None:
    """Initialize SQLAlchemy engine and session factory.

    Idempotent — safe to call multiple times.
    Enables SQLite WAL mode when using sqlite:// URL.
    Creates all registered tables via Base.metadata.create_all().
    """
    global engine, SessionLocal

    if engine is not None:
        return  # already initialized

    connect_args: dict[str, Any] = {}
    pool_kwargs: dict[str, Any] = {}
    if config.db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # Use StaticPool for in-memory SQLite so connections work across threads
        if ":memory:" in config.db_url:
            pool_kwargs["poolclass"] = StaticPool

    engine = create_engine(
        config.db_url,
        echo=config.db_echo,
        connect_args=connect_args,
        **pool_kwargs,
    )

    # Enable WAL mode for SQLite
    if config.db_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create all registered tables
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a DB session, auto-close on request end."""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db(config) first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
