"""Provider-independent AI text generation for fairy-tale stories.

See ``base.py`` for the ``AiTextProvider`` interface every vendor
implements, and ``registry.py`` for how one is selected per request.
"""

from app.services.ai_providers.base import (
    AiTextProvider,
    ProviderAuthError,
    ProviderError,
    ProviderKind,
    ProviderQuotaExceededError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StoryPrompt,
)
from app.services.ai_providers.registry import AiProviderRegistry, build_default_registry

__all__ = [
    "AiProviderRegistry",
    "AiTextProvider",
    "ProviderAuthError",
    "ProviderError",
    "ProviderKind",
    "ProviderQuotaExceededError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "StoryPrompt",
    "build_default_registry",
]
