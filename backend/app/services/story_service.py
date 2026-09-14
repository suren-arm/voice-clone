"""Fairy-tale text generation -- provider-independent.

Depends on :class:`AiProviderRegistry` (an abstraction), never on any single
vendor's SDK: adding, removing, or reconfiguring a provider never touches
this file. The prompt itself is built once, identically for every provider,
by :class:`StoryPromptBuilder`.

Deliberately text-only: this produces the *story*, which the existing speech
pipeline then narrates exactly like any manually-typed text (same
``POST /api/v1/speech``, same voice/background options) -- there is no
separate "narrate the story" endpoint because none is needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.errors import StoryGenerationFailedError, StoryServiceUnavailableError
from app.schemas.story import StoryRequest, StoryResponse
from app.services.ai_providers import AiProviderRegistry, ProviderError, ProviderUnavailableError
from app.services.story_prompt import StoryPromptBuilder

logger = logging.getLogger(__name__)


@dataclass
class StoryService:
    registry: AiProviderRegistry

    def generate(self, request: StoryRequest) -> StoryResponse:
        try:
            provider = self.registry.resolve(request.provider)
        except ProviderUnavailableError as exc:
            raise StoryServiceUnavailableError(str(exc)) from exc

        prompt = StoryPromptBuilder.build(request)

        try:
            text = provider.generate(prompt)
        except ProviderError as exc:
            # The vendor-specific detail (auth failure, quota, raw SDK
            # message) is logged for developers; only the safe, generic
            # user_message ever reaches the client.
            logger.warning("Story generation failed on provider '%s': %s", provider.id, exc)
            if isinstance(exc, ProviderUnavailableError):
                raise StoryServiceUnavailableError(exc.user_message) from exc
            raise StoryGenerationFailedError(exc.user_message) from exc

        title, _, body = text.partition("\n")
        body = body.strip()
        if not body:
            # No blank-line-separated title was produced; treat it all as body.
            title, body = "", text

        return StoryResponse(
            title=title.strip().strip("#*").strip() or "Untitled",
            text=body,
            language=request.language,
            word_count=len(body.split()),
            provider=provider.id,
            provider_name=provider.display_name,
        )
