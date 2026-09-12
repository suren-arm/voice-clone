"""AiProviderRegistry -- selection logic, independent of any real vendor call."""

from __future__ import annotations

import pytest

from app.services.ai_providers.base import AiTextProvider, ProviderUnavailableError, StoryPrompt
from app.services.ai_providers.registry import AiProviderRegistry


class _FakeProvider(AiTextProvider):
    def __init__(self, id_: str, kind: str, available: bool) -> None:
        self.id = id_
        self.display_name = id_.title()
        self.kind = kind
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def generate(self, prompt: StoryPrompt) -> str:  # pragma: no cover - not exercised here
        return "story"


def _registry(*providers: AiTextProvider, preferred: str | None = None, prefer_free: bool = False):
    return AiProviderRegistry(
        providers={p.id: p for p in providers},
        preferred_provider=preferred,
        auto_prefer_free=prefer_free,
    )


def test_explicit_provider_is_used_when_available():
    registry = _registry(_FakeProvider("openai", "paid", True))
    assert registry.resolve("openai").id == "openai"


def test_explicit_unavailable_provider_raises_rather_than_falling_back():
    registry = _registry(
        _FakeProvider("openai", "paid", False),
        _FakeProvider("gemini", "free-tier", True),
    )
    with pytest.raises(ProviderUnavailableError):
        registry.resolve("openai")


def test_explicit_unknown_provider_raises():
    registry = _registry(_FakeProvider("openai", "paid", True))
    with pytest.raises(ProviderUnavailableError, match="Unknown"):
        registry.resolve("not-a-real-provider")


def test_auto_picks_first_available_in_priority_order():
    # Priority order is openai, gemini, anthropic, ollama -- openai unavailable,
    # so gemini should win even though anthropic/ollama are also available.
    registry = _registry(
        _FakeProvider("openai", "paid", False),
        _FakeProvider("gemini", "free-tier", True),
        _FakeProvider("anthropic", "paid", True),
        _FakeProvider("ollama", "local", True),
    )
    assert registry.resolve("auto").id == "gemini"


def test_auto_prefer_free_orders_non_paid_providers_first():
    registry = _registry(
        _FakeProvider("openai", "paid", True),
        _FakeProvider("ollama", "local", True),
        prefer_free=True,
    )
    assert registry.resolve("auto").id == "ollama"


def test_auto_preferred_provider_wins_even_out_of_default_order():
    registry = _registry(
        _FakeProvider("openai", "paid", True),
        _FakeProvider("ollama", "local", True),
        preferred="ollama",
    )
    assert registry.resolve("auto").id == "ollama"


def test_auto_preferred_provider_skipped_if_unavailable():
    registry = _registry(
        _FakeProvider("openai", "paid", True),
        _FakeProvider("ollama", "local", False),
        preferred="ollama",
    )
    assert registry.resolve("auto").id == "openai"


def test_auto_raises_when_nothing_is_configured():
    registry = _registry(
        _FakeProvider("openai", "paid", False),
        _FakeProvider("gemini", "free-tier", False),
    )
    with pytest.raises(ProviderUnavailableError):
        registry.resolve("auto")


def test_list_returns_providers_in_declared_priority_order():
    registry = _registry(
        _FakeProvider("ollama", "local", True),
        _FakeProvider("openai", "paid", True),
        _FakeProvider("anthropic", "paid", True),
    )
    assert [p.id for p in registry.list()] == ["openai", "anthropic", "ollama"]
