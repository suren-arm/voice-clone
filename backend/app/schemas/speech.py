"""Speech generation request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer, field_validator

from app.schemas.common import ApiModel, rfc3339

#: Hard ceiling independent of configuration, so an accidental MAX_TEXT_CHARS
#: of 10_000_000 cannot take the GPU down.
ABSOLUTE_MAX_TEXT_CHARS = 5000


class SpeechRequest(ApiModel):
    voice_id: str = Field(min_length=3, max_length=32)
    text: str = Field(min_length=1, max_length=ABSOLUTE_MAX_TEXT_CHARS)
    language: str = Field(default="en", min_length=2, max_length=8)

    # Optional expressiveness controls. Ranges mirror Chatterbox's documented
    # usable range; out-of-range values are rejected rather than clamped so the
    # caller learns about the mistake.
    exaggeration: float | None = Field(default=None, ge=0.0, le=2.0)
    cfg_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    temperature: float | None = Field(default=None, ge=0.05, le=2.0)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)

    @field_validator("text")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Text cannot be empty or whitespace only.")
        return stripped

    @field_validator("language")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class GenerationResponse(ApiModel):
    id: str
    voice_id: str
    text: str
    language: str
    created_at: datetime

    audio_url: str
    duration_seconds: float
    sample_rate: int
    size_bytes: int

    generation_seconds: float
    real_time_factor: float
    engine: str

    watermarked: bool
    experimental: bool = False
    notice: str | None = Field(
        default=None,
        description="Set when the request took an experimental path (e.g. Armenian).",
    )

    @field_serializer("created_at")
    def _created(self, value: datetime, _info) -> str | None:
        return rfc3339(value)
