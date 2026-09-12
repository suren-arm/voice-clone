"""Fairy-tale generation request/response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import ApiModel

#: Kept intentionally small: this is a children's-story generator, not an
#: open-ended writing tool, so the surface area the model has to handle (and
#: that a caller can misuse) stays narrow.
StoryLanguage = Literal["en", "hy"]
StoryLength = Literal["short", "medium", "long"]
StoryAgeGroup = Literal["3-5", "6-8", "9-12"]
StoryTone = Literal["magical", "funny", "adventure", "educational", "bedtime"]


class StoryRequest(ApiModel):
    #: "auto" (default) lets the server pick any configured provider; an
    #: explicit id (e.g. "openai") uses exactly that provider or reports it
    #: unavailable -- see AiProviderRegistry.resolve.
    provider: str = Field(default="auto", max_length=32)
    language: StoryLanguage = "en"
    characters: str = Field(min_length=1, max_length=300)
    idea: str = Field(min_length=1, max_length=1000)
    age_group: StoryAgeGroup = "6-8"
    length: StoryLength = "medium"
    tone: StoryTone = "magical"

    @field_validator("provider")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("characters", "idea")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field cannot be empty or whitespace only.")
        return stripped


class StoryResponse(ApiModel):
    title: str
    text: str
    language: StoryLanguage
    word_count: int
    #: Which provider actually generated this story -- useful when the
    #: request asked for "auto".
    provider: str
    provider_name: str
