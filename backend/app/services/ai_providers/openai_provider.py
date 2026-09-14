"""OpenAI provider.

Uses the Chat Completions API (``client.chat.completions.create``), the
current, non-deprecated, documented text-generation endpoint as of
implementation time (12 September 2026); the model default is taken from
the ``openai`` Python SDK's own current README examples (``gpt-5.5``) rather
than assumed from memory, since model names in this space move quickly --
see docs comment in ``README.md``'s AI Providers section for how to
re-verify this later.
"""

from __future__ import annotations

import logging

import openai

from app.services.ai_providers.base import (
    AiTextProvider,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StoryPrompt,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 45.0


class OpenAiProvider(AiTextProvider):
    id = "openai"
    display_name = "OpenAI"
    kind = "paid"

    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(self, prompt: StoryPrompt) -> str:
        if not self._api_key:
            raise ProviderUnavailableError("OPENAI_API_KEY is not set.")

        client = openai.OpenAI(api_key=self._api_key, timeout=_REQUEST_TIMEOUT_SECONDS)
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
                max_completion_tokens=prompt.max_tokens,
            )
        except openai.AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except openai.RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except openai.APIConnectionError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except openai.APIStatusError as exc:
            raise ProviderResponseError(str(exc)) from exc
        except Exception as exc:
            raise ProviderError(str(exc)) from exc

        choice = response.choices[0] if response.choices else None
        text = (choice.message.content or "").strip() if choice else ""
        if not text:
            raise ProviderResponseError("OpenAI returned an empty response.")
        return text
