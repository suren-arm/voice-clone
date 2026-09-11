"""Engine and session factory.

SQLite with ``check_same_thread=False`` plus WAL: FastAPI runs sync endpoint
work in a thread pool, and WAL lets readers proceed while a write is in flight.
Swapping in PostgreSQL is a URL change -- see docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _create_engine(settings: Settings) -> Engine:
    url = settings.resolved_database_url()
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(
        url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30} if is_sqlite else {},
        pool_pre_ping=True,
    )
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine
    if _engine is None:
        _engine = _create_engine(settings or get_settings())
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(settings), autoflush=False, expire_on_commit=False, future=True
        )
    return _SessionFactory


def init_db(settings: Settings | None = None) -> None:
    """Create tables if they do not exist.

    ``create_all`` is right for a single-file SQLite MVP. Introducing Alembic is
    the first thing Phase 2 does, at the same time as PostgreSQL.
    """
    from app.models import audit, generation, voice  # noqa: F401  (register metadata)

    Base.metadata.create_all(bind=get_engine(settings))


def reset_db_state() -> None:
    """Dispose the engine and forget the factory (used by the test suite)."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for background/CLI work."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
