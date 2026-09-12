"""AnthropicProvider -- mocked at the SDK boundary, no real API calls."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import app.services.ai_providers.anthropic_provider as module
from app.services.ai_providers.base import ProviderResponseError, ProviderUnavailableError, StoryPrompt
from app.services.ai_providers.anthropic_provider import AnthropicProvider


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


def _prompt() -> StoryPrompt:
    return StoryPrompt(system="You are a storyteller.", user="Tell a story.", max_tokens=900)


def test_unavailable_without_api_key():
    provider = AnthropicProvider(api_key=None, model="claude-opus-5")
    assert provider.is_available() is False
    with pytest.raises(ProviderUnavailableError):
        provider.generate(_prompt())


def test_generates_and_returns_text(monkeypatch):
    fake = _FakeClient("A Fox and a Rabbit\n\nOnce upon a time...")
    monkeypatch.setattr(module.anthropic, "Anthropic", lambda **_: fake)

    provider = AnthropicProvider(api_key="sk-test", model="claude-opus-5")
    assert provider.is_available() is True
    text = provider.generate(_prompt())

    assert "Once upon a time" in text
    assert fake.messages.last_kwargs["model"] == "claude-opus-5"
    assert fake.messages.last_kwargs["system"] == "You are a storyteller."


def test_empty_response_raises(monkeypatch):
    fake = _FakeClient("   ")
    monkeypatch.setattr(module.anthropic, "Anthropic", lambda **_: fake)

    provider = AnthropicProvider(api_key="sk-test", model="claude-opus-5")
    with pytest.raises(ProviderResponseError):
        provider.generate(_prompt())
