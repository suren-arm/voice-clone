"""Google Gemini provider.

Notable among the providers here: Gemini has a genuine standing free tier
(a Google AI Studio API key, issued with no billing account or payment
method) on its Flash-class models -- verified at implementation time,
12 September 2026. That makes it, alongside Ollama, one of this app's two
answers to "at least one provider that needs no paid API key" (see
README.md's AI Providers section). It is still marked ``kind = "free-tier"``
rather than ``"local"``: it is a hosted, rate-limited vendor service, not
infrastructure the operator controls.
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

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

_REQUEST_TIMEOUT_MS = 45_000
_AUTH_STATUS_CODES = {401, 403}
_RATE_LIMIT_STATUS_CODES = {429}


class GeminiProvider(AiTextProvider):
    id = "gemini"
    display_name = "Google Gemini"
    kind = "free-tier"

    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(self, prompt: StoryPrompt) -> str:
        if not self._api_key:
            raise ProviderUnavailableError("GEMINI_API_KEY is not set.")

        client = genai.Client(api_key=self._api_key)
        try:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt.user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=prompt.system,
                    max_output_tokens=prompt.max_tokens,
                    # Gemini's "thinking" models spend part of max_output_tokens on
                    # internal reasoning before any visible text -- fine for math/code,
                    # but for a fairy tale it was silently eating the whole budget and
                    # truncating output to a few words (worse for Armenian, which costs
                    # more tokens per word). No reasoning is needed here, so disable it.
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                    http_options=genai_types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS),
                ),
            )
        except genai_errors.ClientError as exc:
            status = getattr(exc, "code", None) or getattr(exc, "status", None)
            if status in _AUTH_STATUS_CODES:
                raise ProviderAuthError(str(exc)) from exc
            if status in _RATE_LIMIT_STATUS_CODES:
                raise ProviderRateLimitError(str(exc)) from exc
            raise ProviderResponseError(str(exc)) from exc
        except genai_errors.ServerError as exc:
            raise ProviderResponseError(str(exc)) from exc
        except TimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - covers httpx timeouts genai surfaces raw
            if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
                raise ProviderTimeoutError(str(exc)) from exc
            raise ProviderError(str(exc)) from exc

        text = (response.text or "").strip()
        if not text:
            raise ProviderResponseError("Gemini returned an empty response.")
        return text
