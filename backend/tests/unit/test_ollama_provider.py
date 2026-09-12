"""OllamaProvider -- mocked at the HTTP boundary, no real server needed."""

from __future__ import annotations

import httpx
import pytest

import app.services.ai_providers.ollama_provider as module
from app.services.ai_providers.base import (
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StoryPrompt,
)
from app.services.ai_providers.ollama_provider import OllamaProvider


def _prompt() -> StoryPrompt:
    return StoryPrompt(system="You are a storyteller.", user="Tell a story.", max_tokens=900)


def test_unavailable_without_base_url():
    provider = OllamaProvider(base_url=None, model="qwen2.5:7b")
    assert provider.is_available() is False
    with pytest.raises(ProviderUnavailableError):
        provider.generate(_prompt())


def test_generates_and_returns_text(monkeypatch):
    captured = {}

    def fake_post(url, *, json, timeout):
        captured["url"] = url
        captured["json"] = json
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Once upon a time..."}},
            request=request,
        )

    monkeypatch.setattr(module.httpx, "post", fake_post)

    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5:7b")
    text = provider.generate(_prompt())

    assert text == "Once upon a time..."
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["model"] == "qwen2.5:7b"
    assert captured["json"]["stream"] is False


def test_base_url_trailing_slash_is_stripped(monkeypatch):
    captured = {}

    def fake_post(url, **_kwargs):
        captured["url"] = url
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"message": {"content": "story"}}, request=request)

    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = OllamaProvider(base_url="http://localhost:11434/", model="qwen2.5:7b")
    provider.generate(_prompt())
    assert captured["url"] == "http://localhost:11434/api/chat"


def test_model_not_found_maps_to_provider_response_error(monkeypatch):
    def fake_post(url, **_kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(404, json={"error": "model not found"}, request=request)

    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = OllamaProvider(base_url="http://localhost:11434", model="does-not-exist")
    with pytest.raises(ProviderResponseError, match="not pulled"):
        provider.generate(_prompt())


def test_timeout_maps_to_provider_timeout_error(monkeypatch):
    def fake_post(url, **_kwargs):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5:7b")
    with pytest.raises(ProviderTimeoutError):
        provider.generate(_prompt())


def test_connection_error_maps_to_provider_unavailable(monkeypatch):
    def fake_post(url, **_kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5:7b")
    with pytest.raises(ProviderUnavailableError):
        provider.generate(_prompt())
