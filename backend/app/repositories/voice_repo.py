"""Data access for voices. No HTTP, no filesystem, no model -- just rows."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.voice import Voice


class VoiceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, voice_id: str) -> Voice | None:
        return self.session.get(Voice, voice_id)

    def list(self, *, limit: int = 50, offset: int = 0) -> list[Voice]:
        stmt = (
            select(Voice)
            .order_by(Voice.created_at.desc(), Voice.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt))

    def count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Voice)) or 0)

    def add(self, voice: Voice) -> Voice:
        self.session.add(voice)
        self.session.flush()
        return voice

    def delete(self, voice: Voice) -> None:
        self.session.delete(voice)
        self.session.flush()

    def mark_used(self, voice: Voice) -> None:
        voice.generation_count += 1
        voice.last_used_at = utcnow()
        self.session.flush()
