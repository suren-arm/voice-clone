"""Provider-independent AI text-generation abstraction.

``StoryService`` depends on :class:`AiTextProvider`, never on a specific
vendor's SDK/client directly (Dependency Inversion) -- see
``registry.py`` for how a concrete provider is selected at request time,
and ``story_prompt.py`` for how the prompt each provider receives is built
once, identically, regardless of which provider ends up serving it.

Adding a fifth provider means adding one new file implementing this
interface and registering it in ``registry.py::build_default_registry`` --
nothing in ``StoryService`` or the API layer changes (Open/Closed).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Literal

#: "paid" needs a billing-enabled account; "free-tier" has a standing free
#: allowance with no payment method required (documented per-provider in
#: README.md, since free-tier terms change); "local" runs on infrastructure
#: the operator controls, so there is no vendor cost at all.
ProviderKind = Literal["paid", "free-tier", "local"]


class ProviderError(RuntimeError):
    """Base for every provider failure.

    ``user_message`` is safe to return to the frontend as-is: no API keys,
    no stack traces, no vendor-internal details. The original exception
    (``str(self)``, or whatever's chained via ``from exc``) stays in the
    server log for developers.
    """

    user_message: str = "This AI provider is currently unavailable."


class ProviderUnavailableError(ProviderError):
    user_message = "This AI provider is not configured on this server."


class ProviderAuthError(ProviderError):
    user_message = "This AI provider rejected the server's credentials."


class ProviderRateLimitError(ProviderError):
    user_message = (
        "This AI provider's rate limit was reached. Try again shortly, or choose another provider."
    )


class ProviderQuotaExceededError(ProviderError):
    user_message = (
        "This AI provider's usage quota has been reached. Please choose another provider."
    )


class ProviderTimeoutError(ProviderError):
    user_message = (
        "This AI provider took too long to respond. Try again, or choose another provider."
    )


class ProviderResponseError(ProviderError):
    user_message = "This AI provider returned an unexpected response."


@dataclass(frozen=True)
class StoryPrompt:
    """What every provider receives -- built once by ``StoryPromptBuilder``.

    Deliberately just a system instruction, a user turn, and a token budget:
    the smallest common denominator every provider's chat-style API accepts,
    so no provider implementation needs its own prompt-construction logic.
    """

    system: str
    user: str
    max_tokens: int


class AiTextProvider(abc.ABC):
    """One AI vendor/backend capable of generating fairy-tale text."""

    id: str
    display_name: str
    kind: ProviderKind

    @abc.abstractmethod
    def is_available(self) -> bool:
        """True if this provider is configured (has credentials/endpoint).

        Must never make a network call -- this is used to build the
        capability list on every page load (``GET /api/v1/ai/providers``).
        """

    @abc.abstractmethod
    def generate(self, prompt: StoryPrompt) -> str:
        """Return the generated story text.

        Raises a :class:`ProviderError` subclass on any failure -- missing
        config, auth, rate limit, quota, timeout, or a malformed/empty
        response. Never raises the vendor SDK's own exception type directly,
        so callers (``StoryService``) never need to know which SDKs exist.
        """
