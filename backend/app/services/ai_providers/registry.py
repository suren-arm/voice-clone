"""Central provider registry -- the only place that knows which providers exist.

``StoryService`` asks this for a provider by id (or ``"auto"``); it never
branches on provider identity itself, and neither does the API layer or the
frontend beyond displaying whatever :meth:`AiProviderRegistry.list` returns.
Adding a provider means registering it in :func:`build_default_registry`,
not touching any ``if provider == ...`` chain.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.ai_providers.anthropic_provider import AnthropicProvider
from app.services.ai_providers.base import AiTextProvider, ProviderUnavailableError
from app.services.ai_providers.gemini_provider import GeminiProvider
from app.services.ai_providers.ollama_provider import OllamaProvider
from app.services.ai_providers.openai_provider import OpenAiProvider

AUTO_ID = "auto"

#: Default auto-mode priority when no AI_PREFERRED_PROVIDER is set and
#: AI_AUTO_PREFER_FREE is false: try the most capable paid providers first,
#: then the free-tier vendor, then local. This only ever engages for
#: requests that explicitly ask for "auto" -- picking an exact provider by
#: id always uses exactly that provider or reports it unavailable, never a
#: silent substitute (see StoryService).
_DEFAULT_PRIORITY = ("openai", "gemini", "anthropic", "ollama")


@dataclass
class AiProviderRegistry:
    providers: dict[str, AiTextProvider]
    preferred_provider: str | None
    auto_prefer_free: bool

    def list(self) -> list[AiTextProvider]:
        return [self.providers[pid] for pid in _DEFAULT_PRIORITY if pid in self.providers]

    def get(self, provider_id: str) -> AiTextProvider | None:
        return self.providers.get(provider_id)

    def resolve(self, requested: str) -> AiTextProvider:
        """Pick the provider a story-generation request will actually use.

        An explicit ``requested`` id is either used exactly as asked, or
        reported unavailable -- it never silently falls back to a different
        provider (a user who picked OpenAI did not consent to being billed
        on Anthropic instead). ``"auto"`` is the only mode allowed to try
        more than one candidate.
        """
        if requested != AUTO_ID:
            provider = self.get(requested)
            if provider is None:
                raise ProviderUnavailableError(f"Unknown AI provider '{requested}'.")
            if not provider.is_available():
                raise ProviderUnavailableError(
                    f"{provider.display_name} is not configured on this server."
                )
            return provider

        candidates = self.list()
        if self.auto_prefer_free:
            candidates = sorted(candidates, key=lambda p: 0 if p.kind != "paid" else 1)
        if self.preferred_provider:
            preferred = self.get(self.preferred_provider)
            if preferred is not None:
                candidates = [preferred, *(p for p in candidates if p.id != preferred.id)]

        for provider in candidates:
            if provider.is_available():
                return provider

        raise ProviderUnavailableError(
            "No AI provider is configured on this server. Set one of "
            "OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, or OLLAMA_BASE_URL."
        )


def build_default_registry(settings: Settings) -> AiProviderRegistry:
    providers: list[AiTextProvider] = [
        OpenAiProvider(settings.openai_api_key, settings.openai_model),
        GeminiProvider(settings.gemini_api_key, settings.gemini_model),
        AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model),
        OllamaProvider(settings.ollama_base_url, settings.ollama_model),
    ]
    return AiProviderRegistry(
        providers={p.id: p for p in providers},
        preferred_provider=settings.ai_preferred_provider,
        auto_prefer_free=settings.ai_auto_prefer_free,
    )
