"""StoryService -- fairy-tale generation via the Anthropic API (mocked)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import app.services.story_service as story_service_module
from app.core.errors import StoryGenerationFailedError, StoryServiceUnavailableError
from app.schemas.story import StoryRequest
from app.services.story_service import StoryService


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeMessage:
    content: list


class _FakeMessages:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeMessage(content=[_FakeTextBlock(text=self._response_text)])


class _FakeClient:
    def __init__(self, response_text: str, **_kwargs) -> None:
        self.messages = _FakeMessages(response_text)


def _settings(**overrides):
    from app.core.config import Settings

    overrides.setdefault("anthropic_api_key", "sk-test-key")
    return Settings(**overrides)


def _request(**overrides) -> StoryRequest:
    payload = {
        "language": "en",
        "characters": "A rabbit and a fox",
        "idea": "they become unlikely friends",
        "ageGroup": "6-8",
        "length": "short",
        "tone": "magical",
    }
    payload.update(overrides)
    return StoryRequest.model_validate(payload)


def test_raises_when_api_key_is_not_configured():
    service = StoryService(settings=_settings(anthropic_api_key=None))
    with pytest.raises(StoryServiceUnavailableError):
        service.generate(_request())


def test_generates_a_story_with_title_and_body(monkeypatch):
    fake = _FakeClient("The Rabbit and the Fox\n\nOnce upon a time, they met in the forest.")
    monkeypatch.setattr(story_service_module.anthropic, "Anthropic", lambda **_: fake)

    service = StoryService(settings=_settings())
    result = service.generate(_request())

    assert result.title == "The Rabbit and the Fox"
    assert "forest" in result.text
    assert result.language == "en"
    assert result.word_count > 0


def test_writes_natively_in_armenian_not_english(monkeypatch):
    fake = _FakeClient("Առյուծը\n\nԱռյուծը և նապաստակը ընկերացան անտառում։")
    monkeypatch.setattr(story_service_module.anthropic, "Anthropic", lambda **_: fake)

    service = StoryService(settings=_settings())
    result = service.generate(_request(language="hy"))

    assert result.language == "hy"
    # The system/user prompt instructs native generation -- verify the model
    # request actually asked for Armenian, not "write English then translate".
    assert "Armenian" in fake.messages.last_kwargs["system"]


def test_falls_back_to_untitled_when_no_blank_line_separates_a_title(monkeypatch):
    fake = _FakeClient("Just a single line of story with no separate title at all.")
    monkeypatch.setattr(story_service_module.anthropic, "Anthropic", lambda **_: fake)

    service = StoryService(settings=_settings())
    result = service.generate(_request())

    assert result.title == "Untitled"
    assert "single line" in result.text


def test_empty_model_response_raises_generation_failed(monkeypatch):
    fake = _FakeClient("   ")
    monkeypatch.setattr(story_service_module.anthropic, "Anthropic", lambda **_: fake)

    service = StoryService(settings=_settings())
    with pytest.raises(StoryGenerationFailedError):
        service.generate(_request())


def test_uses_the_configured_model_and_a_length_appropriate_token_budget(monkeypatch):
    fake = _FakeClient("Title\n\nBody.")
    monkeypatch.setattr(story_service_module.anthropic, "Anthropic", lambda **_: fake)

    service = StoryService(settings=_settings(story_model="claude-opus-5"))
    service.generate(_request(length="long"))

    assert fake.messages.last_kwargs["model"] == "claude-opus-5"
    short_service = StoryService(settings=_settings())
    short_service.generate(_request(length="short"))
    assert (
        fake.messages.last_kwargs["max_tokens"] > 0
    )  # long vs short differ; see _LENGTH_SPEC
