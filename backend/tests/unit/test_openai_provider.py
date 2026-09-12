"""OpenAiProvider -- mocked at the SDK boundary, no real API calls."""

from __future__ import annotations

from dataclasses import dataclass

import openai
import pytest

import app.services.ai_providers.openai_provider as module
from app.services.ai_providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
    StoryPrompt,
)
from app.services.ai_providers.openai_provider import OpenAiProvider


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeCompletion:
    choices: list


class _FakeCompletions:
    def __init__(self, response_text: str | None = "A story.", *, error: Exception | None = None) -> None:
        self._response_text = response_text
        self._error = error
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._error:
            raise self._error
        return _FakeCompletion(choices=[_FakeChoice(message=_FakeMessage(content=self._response_text))])


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, completions: _FakeCompletions, **_kwargs) -> None:
        self.chat = _FakeChat(completions)


def _prompt() -> StoryPrompt:
    return StoryPrompt(system="You are a storyteller.", user="Tell a story.", max_tokens=900)


def test_unavailable_without_api_key():
    provider = OpenAiProvider(api_key=None, model="gpt-5.5")
    assert provider.is_available() is False
    with pytest.raises(ProviderUnavailableError):
        provider.generate(_prompt())


def test_generates_and_returns_text(monkeypatch):
    completions = _FakeCompletions("Once upon a time, a fox and a rabbit became friends.")
    monkeypatch.setattr(module.openai, "OpenAI", lambda **_: _FakeClient(completions))

    provider = OpenAiProvider(api_key="sk-test", model="gpt-5.5")
    text = provider.generate(_prompt())

    assert "fox and a rabbit" in text
    assert completions.last_kwargs["model"] == "gpt-5.5"
    assert completions.last_kwargs["messages"][0] == {
        "role": "system",
        "content": "You are a storyteller.",
    }


def test_empty_response_raises(monkeypatch):
    completions = _FakeCompletions(None)
    monkeypatch.setattr(module.openai, "OpenAI", lambda **_: _FakeClient(completions))

    provider = OpenAiProvider(api_key="sk-test", model="gpt-5.5")
    with pytest.raises(ProviderResponseError):
        provider.generate(_prompt())


def test_auth_error_maps_to_provider_auth_error(monkeypatch):
    error = openai.AuthenticationError(
        "bad key", response=_fake_response(401), body=None
    )
    completions = _FakeCompletions(error=error)
    monkeypatch.setattr(module.openai, "OpenAI", lambda **_: _FakeClient(completions))

    provider = OpenAiProvider(api_key="sk-bad", model="gpt-5.5")
    with pytest.raises(ProviderAuthError):
        provider.generate(_prompt())


def test_rate_limit_error_maps_to_provider_rate_limit_error(monkeypatch):
    error = openai.RateLimitError("too many requests", response=_fake_response(429), body=None)
    completions = _FakeCompletions(error=error)
    monkeypatch.setattr(module.openai, "OpenAI", lambda **_: _FakeClient(completions))

    provider = OpenAiProvider(api_key="sk-test", model="gpt-5.5")
    with pytest.raises(ProviderRateLimitError):
        provider.generate(_prompt())


def _fake_response(status_code: int):
    import httpx2

    request = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")
    return httpx2.Response(status_code=status_code, request=request)
