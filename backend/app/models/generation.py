"""Generated-speech ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    voice_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("voices.id", ondelete="CASCADE"), nullable=False, index=True
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    # The text actually handed to the model. Differs from ``text`` only on the
    # experimental Armenian path, where it holds the transliteration.
    effective_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # -- telemetry ---------------------------------------------------------
    generation_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    real_time_factor: Mapped[float] = mapped_column(Float, nullable=False)
    engine: Mapped[str] = mapped_column(String(64), nullable=False)

    # -- provenance --------------------------------------------------------
    watermarked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    experimental: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    voice: Mapped["Voice"] = relationship(back_populates="generations")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Generation {self.id} voice={self.voice_id} {self.duration_seconds:.1f}s>"
