"""Data access for generated speech."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.generation import Generation


class GenerationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, generation_id: str) -> Generation | None:
        return self.session.get(Generation, generation_id)

    def list(
        self, *, voice_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Generation]:
        stmt = select(Generation).order_by(Generation.created_at.desc(), Generation.id.desc())
        if voice_id:
            stmt = stmt.where(Generation.voice_id == voice_id)
        return list(self.session.scalars(stmt.limit(limit).offset(offset)))

    def count(self, *, voice_id: str | None = None) -> int:
        stmt = select(func.count()).select_from(Generation)
        if voice_id:
            stmt = stmt.where(Generation.voice_id == voice_id)
        return int(self.session.scalar(stmt) or 0)

    def add(self, generation: Generation) -> Generation:
        self.session.add(generation)
        self.session.flush()
        return generation

    def delete(self, generation: Generation) -> None:
        self.session.delete(generation)
        self.session.flush()

    def filenames_for_voice(self, voice_id: str) -> list[str]:
        """Filenames to unlink when a voice is deleted."""
        stmt = select(Generation.filename).where(Generation.voice_id == voice_id)
        return list(self.session.scalars(stmt))
