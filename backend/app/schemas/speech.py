"""Speech generation request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from app.schemas.common import ApiModel, rfc3339

#: Hard ceiling independent of configuration, so an accidental MAX_TEXT_CHARS
#: of 10_000_000 cannot take the GPU down. Sized to comfortably fit a "long"
#: generated fairy tale (~800 words) after chunking.
ABSOLUTE_MAX_TEXT_CHARS = 5000

#: "none" plus every key in ai.audio_mix.BACKGROUND_SOUNDS. Kept as a literal
#: here (rather than importing that dict) so the schema has no import-time
#: dependency on ffmpeg/asset presence -- validation is just which names are
#: accepted, not whether the asset file happens to exist on this deployment.
BackgroundSound = Literal["none", "mystical", "calm", "forest", "bedtime"]


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

    background_sound: BackgroundSound = "none"
    #: 0-100 slider value. The actual mix gain is additionally clamped
    #: server-side (see ai.audio_mix._MAX_BACKGROUND_GAIN) so narration always
    #: stays louder and clearer than the background, however high this is set.
    background_volume: int = Field(default=15, ge=0, le=100)

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
    background_sound: BackgroundSound = "none"
    background_applied: bool = Field(
        default=False,
        description="Whether the requested background sound was actually mixed in.",
    )
    background_notice: str | None = Field(
        default=None,
        description="Set when a background sound was requested but could not be applied.",
    )

    @field_serializer("created_at")
    def _created(self, value: datetime, _info) -> str | None:
        return rfc3339(value)
