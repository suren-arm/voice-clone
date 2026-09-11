"""Voice request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer, field_validator

from app.schemas.common import ApiModel, rfc3339

CONSENT_STATEMENT = (
    "I confirm that this is my own voice, or that I have explicit permission "
    "from the speaker to create a synthetic copy of their voice."
)


class VoiceCreateForm(ApiModel):
    """Multipart form fields for ``POST /voices`` (the file is separate)."""

    name: str = Field(min_length=1, max_length=80)
    language: str = Field(default="en", min_length=2, max_length=8)
    consent: bool = Field(
        default=False,
        description="Must be true: the caller asserts ownership of, or permission for, this voice.",
    )
    source: str = Field(default="upload", pattern="^(upload|record)$")

    @field_validator("language")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name cannot be blank.")
        return stripped


class VoiceResponse(ApiModel):
    id: str
    name: str
    language: str
    created_at: datetime
    engine: str
    engine_variant: str | None = None
    reference_duration_seconds: float
    reference_sample_rate: int
    source: str
    generation_count: int
    last_used_at: datetime | None = None
    consent_given: bool
    has_conditioning_cache: bool
    sample_url: str | None = None

    @field_serializer("created_at", "last_used_at")
    def _dates(self, value: datetime | None, _info) -> str | None:
        return rfc3339(value)
