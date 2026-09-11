"""SQLAlchemy declarative base and timestamp helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Timezone-aware UTC now.

    SQLite has no native timestamp type, so we normalise on the Python side and
    always serialise as RFC 3339 with a ``Z`` suffix.
    """
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass
