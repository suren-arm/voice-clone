"""Shared response shapes.

All responses use ``camelCase`` on the wire and ``snake_case`` in Python: the
API is consumed by TypeScript today and by Kotlin/Swift later, and all three
prefer camelCase.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base for every schema: camelCase aliases, accepts either spelling."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        ser_json_timedelta="float",
    )


def rfc3339(value: datetime | None) -> str | None:
    """Serialise a datetime as RFC 3339 UTC with a ``Z`` suffix."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class PageMeta(ApiModel):
    total: int
    limit: int
    offset: int


class Page(ApiModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class ErrorDetail(ApiModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(ApiModel):
    error: ErrorDetail


class DeletedResponse(ApiModel):
    id: str
    deleted: bool = True


class LanguageOption(ApiModel):
    code: str
    name: str
    native: bool = Field(
        default=True,
        description="False for experimental paths the model does not natively support.",
    )
    experimental: bool = False
    note: str | None = None


class EngineDescription(ApiModel):
    name: str
    variant: str
    device: str
    sample_rate: int
    loaded: bool
    supports_streaming: bool
    supports_cached_conditioning: bool
    watermarked: bool
    license: str
    notes: str | None = None


class LimitsDescription(ApiModel):
    max_upload_bytes: int
    min_reference_seconds: float
    max_reference_seconds: float
    max_text_chars: int
    max_voices: int
    require_consent: bool
    # -- Book Reader --------------------------------------------------------
    max_pdf_bytes: int
    max_pdf_pages: int
    max_remote_download_bytes: int
    max_book_narration_chars: int


class SystemInfo(ApiModel):
    app_name: str
    version: str
    environment: str
    engine: EngineDescription
    device_details: dict[str, Any]
    languages: list[LanguageOption]
    limits: LimitsDescription
    accepted_audio_formats: list[str]


class HealthResponse(ApiModel):
    status: str
    engine_loaded: bool
    version: str
