"""StoryService -- provider-independent orchestration.

Exercised entirely against a fake AiTextProvider/registry: this file has no
knowledge of any real vendor SDK, which is exactly the point of the
AiTextProvider abstraction (see tests/unit/test_*_provider.py for the
per-vendor adapters, and test_ai_provider_registry.py for selection logic).
"""

from __future__ import annotations

import pytest

from app.core.errors import StoryGenerationFailedError, StoryServiceUnavailableError
from app.schemas.story import StoryRequest
from app.services.ai_providers.base import (
    AiTextProvider,
    ProviderRateLimitError,
    ProviderUnavailableError,
    StoryPrompt,
)
from app.services.ai_providers.registry import AiProviderRegistry
from app.services.story_service import StoryService


class _FakeProvider(AiTextProvider):
    id = "fake"
    display_name = "Fake Provider"
    kind = "paid"

    def __init__(self, *, text: str | None = None, error: Exception | None = None) -> None:
        self._text = text
        self._error = error
        self.last_prompt: StoryPrompt | None = None

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: StoryPrompt) -> str:
        self.last_prompt = prompt
        if self._error:
            raise self._error
        return self._text or ""


def _registry(provider: AiTextProvider) -> AiProviderRegistry:
    return AiProviderRegistry(
        providers={provider.id: provider}, preferred_provider=None, auto_prefer_free=False
    )


def _request(**overrides) -> StoryRequest:
    payload = {
        "provider": "fake",
        "language": "en",
        "characters": "A rabbit and a fox",
        "idea": "they become unlikely friends",
        "ageGroup": "6-8",
        "length": "short",
        "tone": "magical",
    }
    payload.update(overrides)
    return StoryRequest.model_validate(payload)


def test_generates_a_story_with_title_and_body_and_names_the_provider():
    provider = _FakeProvider(
        text="The Rabbit and the Fox\n\nOnce upon a time, they met in the forest."
    )
    service = StoryService(registry=_registry(provider))

    result = service.generate(_request())

    assert result.title == "The Rabbit and the Fox"
    assert "forest" in result.text
    assert result.provider == "fake"
    assert result.provider_name == "Fake Provider"
    assert result.word_count > 0


def test_falls_back_to_untitled_when_no_blank_line_separates_a_title():
    provider = _FakeProvider(text="Just a single line of story with no separate title at all.")
    service = StoryService(registry=_registry(provider))

    result = service.generate(_request())

    assert result.title == "Untitled"
    assert "single line" in result.text


def test_prompt_reaches_the_provider_unmodified_by_the_service():
    provider = _FakeProvider(text="Title\n\nBody.")
    service = StoryService(registry=_registry(provider))

    service.generate(_request(characters="Կարապետ և Ռուզաննա", language="en"))

    assert provider.last_prompt is not None
    assert "Կարապետ և Ռուզաննա" in provider.last_prompt.user


def test_provider_unavailable_maps_to_503():
    provider = _FakeProvider(error=ProviderUnavailableError("not configured"))
    service = StoryService(registry=_registry(provider))

    with pytest.raises(StoryServiceUnavailableError):
        service.generate(_request())


def test_other_provider_errors_map_to_generation_failed():
    provider = _FakeProvider(error=ProviderRateLimitError("rate limited"))
    service = StoryService(registry=_registry(provider))

    with pytest.raises(StoryGenerationFailedError) as excinfo:
        service.generate(_request())
    # The safe, generic user_message reaches the caller -- not the raw
    # provider-internal string.
    assert "rate limit" in str(excinfo.value).lower()


def test_unknown_provider_id_maps_to_503():
    provider = _FakeProvider(text="Title\n\nBody.")
    service = StoryService(registry=_registry(provider))

    with pytest.raises(StoryServiceUnavailableError):
        service.generate(_request(provider="not-registered"))
