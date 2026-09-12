"""Ollama provider -- the genuinely no-vendor-cost option.

Talks to Ollama's REST API directly (``POST {base_url}/api/chat``) rather
than pulling in a client library: the API is small, stable, and already
well documented, so a dependency would buy nothing.

This does **not** run inside this backend's own container: Ollama needs its
own process and enough RAM to hold a model, which does not fit alongside
Chatterbox on the deployed Render Starter instance (see README.md's AI
Providers section for the sizing discussion). It is real and functional
whenever ``OLLAMA_BASE_URL`` points at a real Ollama server -- your own
machine in development, or a self-hosted box in production -- which is what
makes it the "no mandatory paid API key, ever" answer: it costs whatever
you already pay to run that server, not a per-token vendor fee.
"""

from __future__ import annotations

import logging

import httpx

from app.services.ai_providers.base import (
    AiTextProvider,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StoryPrompt,
)

logger = logging.getLogger(__name__)

#: Local/self-hosted generation on modest hardware can genuinely take this
#: long for a few hundred words -- much longer than a hosted vendor API.
_REQUEST_TIMEOUT_SECONDS = 120.0


class OllamaProvider(AiTextProvider):
    id = "ollama"
    display_name = "Local AI (Ollama)"
    kind = "local"

    def __init__(self, base_url: str | None, model: str) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._model = model

    def is_available(self) -> bool:
        return bool(self._base_url)

    def generate(self, prompt: StoryPrompt) -> str:
        if not self._base_url:
            raise ProviderUnavailableError("OLLAMA_BASE_URL is not set.")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "stream": False,
            "options": {"num_predict": prompt.max_tokens},
        }
        try:
            response = httpx.post(
                f"{self._base_url}/api/chat", json=payload, timeout=_REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ProviderResponseError(
                    f"Model '{self._model}' is not pulled on the Ollama server."
                ) from exc
            raise ProviderResponseError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

        data = response.json()
        text = (data.get("message", {}).get("content") or "").strip()
        if not text:
            raise ProviderResponseError("Ollama returned an empty response.")
        return text
