"""Anthropic Claude provider -- optional, like every other provider here.

Model default (``claude-opus-5``) and API usage verified against Anthropic's
own current documentation at implementation time, 12 September 2026.
"""

from __future__ import annotations

import logging

import anthropic

from app.services.ai_providers.base import (
    AiTextProvider,
    ProviderAuthError,
    ProviderError,
    ProviderQuotaExceededError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StoryPrompt,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 45.0


class AnthropicProvider(AiTextProvider):
    id = "anthropic"
    display_name = "Anthropic Claude"
    kind = "paid"

    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(self, prompt: StoryPrompt) -> str:
        if not self._api_key:
            raise ProviderUnavailableError("ANTHROPIC_API_KEY is not set.")

        client = anthropic.Anthropic(api_key=self._api_key, timeout=_REQUEST_TIMEOUT_SECONDS)
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=prompt.max_tokens,
                system=prompt.system,
                messages=[{"role": "user", "content": prompt.user}],
                output_config={"effort": "medium"},
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code == 429:
                raise ProviderQuotaExceededError(str(exc)) from exc
            raise ProviderResponseError(str(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - never let a raw SDK error escape
            raise ProviderError(str(exc)) from exc

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise ProviderResponseError("Claude returned an empty response.")
        return text
