"""GeminiProvider -- mocked at the SDK boundary, no real API calls."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from google.genai import errors as genai_errors

import app.services.ai_providers.gemini_provider as module
from app.services.ai_providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
    StoryPrompt,
)
from app.services.ai_providers.gemini_provider import GeminiProvider


@dataclass
class _FakeResponse:
    text: str | None


class _FakeModels:
    def __init__(
        self, response_text: str | None = "A story.", *, error: Exception | None = None
    ) -> None:
        self._response_text = response_text
        self._error = error
        self.last_kwargs: dict | None = None

    def generate_content(self, **kwargs):
        self.last_kwargs = kwargs
        if self._error:
            raise self._error
        return _FakeResponse(text=self._response_text)


class _FakeClient:
    def __init__(self, models: _FakeModels, **_kwargs) -> None:
        self.models = models


def _prompt() -> StoryPrompt:
    return StoryPrompt(system="You are a storyteller.", user="Tell a story.", max_tokens=900)


def test_unavailable_without_api_key():
    provider = GeminiProvider(api_key=None, model="gemini-3.5-flash")
    assert provider.is_available() is False
    with pytest.raises(ProviderUnavailableError):
        provider.generate(_prompt())


def test_generates_and_returns_text(monkeypatch):
    models = _FakeModels("Once upon a time, a fox and a rabbit became friends.")
    monkeypatch.setattr(module.genai, "Client", lambda **_: _FakeClient(models))

    provider = GeminiProvider(api_key="key", model="gemini-3.5-flash")
    text = provider.generate(_prompt())

    assert "fox and a rabbit" in text
    assert models.last_kwargs["model"] == "gemini-3.5-flash"
    assert models.last_kwargs["config"].system_instruction == "You are a storyteller."
    # Thinking must be disabled: it otherwise eats max_output_tokens on internal
    # reasoning before any visible text, truncating (or emptying) the story.
    assert models.last_kwargs["config"].thinking_config.thinking_budget == 0


def test_empty_response_raises(monkeypatch):
    models = _FakeModels(None)
    monkeypatch.setattr(module.genai, "Client", lambda **_: _FakeClient(models))

    provider = GeminiProvider(api_key="key", model="gemini-3.5-flash")
    with pytest.raises(ProviderResponseError):
        provider.generate(_prompt())


def test_auth_client_error_maps_to_provider_auth_error(monkeypatch):
    error = genai_errors.ClientError(401, {"error": {"message": "bad key"}})
    models = _FakeModels(error=error)
    monkeypatch.setattr(module.genai, "Client", lambda **_: _FakeClient(models))

    provider = GeminiProvider(api_key="bad", model="gemini-3.5-flash")
    with pytest.raises(ProviderAuthError):
        provider.generate(_prompt())


def test_rate_limit_client_error_maps_to_provider_rate_limit_error(monkeypatch):
    error = genai_errors.ClientError(429, {"error": {"message": "quota"}})
    models = _FakeModels(error=error)
    monkeypatch.setattr(module.genai, "Client", lambda **_: _FakeClient(models))

    provider = GeminiProvider(api_key="key", model="gemini-3.5-flash")
    with pytest.raises(ProviderRateLimitError):
        provider.generate(_prompt())
