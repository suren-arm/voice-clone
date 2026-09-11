"""Voice profile ORM model.

What is *not* stored here is as deliberate as what is:

* No speaker embedding lives in the database. Chatterbox's conditioning is a
  ~MB tensor bundle and a derived artefact of a specific model revision, so it
  belongs on disk next to the reference audio, regenerable at any time.
* No raw audio bytes. The DB holds metadata and paths; audio lives in the
  storage tree behind an authenticated endpoint.
* ``consent_*`` columns exist because cloning someone's voice without
  permission is the abuse case this product has to design against.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class Voice(Base):
    __tablename__ = "voices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")

    # -- engine / conditioning --------------------------------------------
    engine: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_variant: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_conditioning_cache: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # -- reference audio ---------------------------------------------------
    reference_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    reference_sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    source_container: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="upload"
    )  # upload|record

    # -- consent / safety --------------------------------------------------
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_statement: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -- bookkeeping -------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    generation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    generations: Mapped[list[Generation]] = relationship(  # noqa: F821
        back_populates="voice", cascade="all, delete-orphan", passive_deletes=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Voice {self.id} {self.name!r} lang={self.language}>"
