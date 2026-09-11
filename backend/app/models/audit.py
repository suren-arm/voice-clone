"""Append-only audit trail.

Voice cloning needs an answer to "who created this voice, when, and did they
assert consent?" long after the fact -- including after the voice is deleted.
Audit rows therefore hold no foreign key and survive voice deletion.

The client IP is stored as a salted hash, not in the clear: the trail needs to
link events from the same origin, not to identify a person.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    subject_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    actor_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditEvent {self.event} subject={self.subject_id}>"
