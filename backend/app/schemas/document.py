"""Book Reader request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.schemas.common import ApiModel, rfc3339
from app.schemas.speech import BackgroundSound

SourceType = Literal["pdf_upload", "pdf_url", "html_url"]
ReadingRangeKind = Literal["entire", "pages", "section"]
#: Only speeds ai.audio_mix.apply_speed's atempo filter is verified reliable
#: at (see that module) -- never a free-form float from the client.
ReadingSpeed = Literal[0.75, 1.0, 1.25, 1.5]


class BookFromUrlRequest(ApiModel):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class DocumentSectionSummary(ApiModel):
    """One row in the section list -- title/length only, no text.

    The preview screen pages through these (see ``GET /books/{id}/sections``)
    rather than ever receiving a whole book's text in one response.
    """

    index: int
    title: str | None
    page_number: int | None
    char_count: int


class DocumentSectionResponse(DocumentSectionSummary):
    """One section including its actual text -- fetched on demand per page."""

    text: str


class DocumentResponse(ApiModel):
    id: str
    title: str | None
    source_type: SourceType
    source_url: str | None
    original_filename: str | None
    language: str
    page_count: int | None
    section_count: int
    char_count: int
    created_at: datetime

    @field_serializer("created_at")
    def _created(self, value: datetime, _info) -> str | None:
        return rfc3339(value)


class ReadingRangeRequest(ApiModel):
    kind: ReadingRangeKind
    from_page: int | None = Field(default=None, ge=1)
    to_page: int | None = Field(default=None, ge=1)
    section_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_shape(self) -> ReadingRangeRequest:
        if self.kind == "pages":
            if self.from_page is None or self.to_page is None:
                raise ValueError("'fromPage' and 'toPage' are required for a page range.")
            if self.to_page < self.from_page:
                raise ValueError("'toPage' must be greater than or equal to 'fromPage'.")
        if self.kind == "section" and self.section_index is None:
            raise ValueError("'sectionIndex' is required to narrate a single section.")
        return self


class BookNarrateRequest(ApiModel):
    voice_id: str = Field(min_length=3, max_length=32)
    #: Overrides the document's detected language -- see README.md's Book
    #: Reader section on why detection is never trusted blindly.
    language: str = Field(default="en", min_length=2, max_length=8)
    range: ReadingRangeRequest
    speed: ReadingSpeed = 1.0
    background_sound: BackgroundSound = "none"
    background_volume: int = Field(default=15, ge=0, le=100)

    @field_validator("language")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class BookNarrationResponse(ApiModel):
    """A book narration is an ordinary Generation -- playback/download/history
    all reuse the existing `/generations/{id}` machinery unchanged. This
    wraps that response with the book-specific context the player needs."""

    generation_id: str
    document_id: str
    range: ReadingRangeRequest
    audio_url: str
    duration_seconds: float
    notice: str | None = None
    background_applied: bool = False
    background_notice: str | None = None
