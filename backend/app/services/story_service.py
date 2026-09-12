"""Fairy-tale text generation via the Anthropic Claude API.

Deliberately text-only: this produces the *story*, which the existing speech
pipeline then narrates exactly like any manually-typed text (same
``POST /api/v1/speech``, same voice/background options) -- there is no
separate "narrate the story" endpoint because none is needed.

Both English and Armenian stories are generated *natively* by asking Claude
to write directly in the target language, not by writing English and
translating: Claude Opus 5 is fluent in Armenian, and translation tends to
read as translated. This is a different, easier problem than Armenian
*speech* synthesis (see docs/ARMENIAN.md) -- there is no phonetic model in
the loop here, just text.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import anthropic

from app.core.config import Settings
from app.core.errors import StoryGenerationFailedError, StoryServiceUnavailableError
from app.schemas.story import StoryRequest, StoryResponse

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hy": "Armenian (Հայերեն, Eastern Armenian as spoken in Armenia)",
}

#: Target word count and a matching output-token ceiling per length tier.
#: Tokens are generous relative to the word target: Armenian script and a
#: title line both cost more tokens per word than plain English prose.
_LENGTH_SPEC: dict[str, tuple[int, int]] = {
    "short": (200, 900),
    "medium": (450, 1600),
    "long": (800, 2600),
}

_TONE_GUIDANCE: dict[str, str] = {
    "magical": "wondrous and enchanting, with a gentle sense of awe",
    "funny": "light and funny, with warm, silly humor a child would giggle at",
    "adventure": "exciting and adventurous, with real (but never scary) stakes",
    "educational": "gently educational, weaving in a clear, age-appropriate lesson",
    "bedtime": "calm, soothing and slow-paced, suitable for reading right before sleep",
}

_AGE_GUIDANCE: dict[str, str] = {
    "3-5": "very simple sentences, concrete ideas, lots of repetition, no scary content",
    "6-8": "simple, vivid sentences and clear cause-and-effect, mild suspense is fine",
    "9-12": "richer vocabulary and slightly more complex plotting, still wholesome",
}


@dataclass
class StoryService:
    settings: Settings

    def generate(self, request: StoryRequest) -> StoryResponse:
        if not self.settings.anthropic_api_key:
            raise StoryServiceUnavailableError(
                "Fairy-tale generation is not configured on this server "
                "(ANTHROPIC_API_KEY is not set)."
            )

        language_name = _LANGUAGE_NAMES[request.language]
        target_words, max_tokens = _LENGTH_SPEC[request.length]
        tone = _TONE_GUIDANCE[request.tone]
        age = _AGE_GUIDANCE[request.age_group]

        system = (
            "You are a warm, imaginative children's fairy-tale author. Write "
            "a complete, original, wholesome fairy tale meant to be read aloud. "
            f"Write the ENTIRE story natively in {language_name} -- compose "
            "directly in that language, do not draft in English and translate. "
            "Output plain narration text only: no markdown, no stage directions, "
            "no headings other than the title. Start with a single short title "
            "line, then a blank line, then the story."
        )
        user = (
            f"Main characters: {request.characters}\n"
            f"Story idea: {request.idea}\n"
            f"Age group: {request.age_group} ({age})\n"
            f"Tone: {request.tone} -- {tone}\n"
            f"Target length: about {target_words} words."
        )

        client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        try:
            response = client.messages.create(
                model=self.settings.story_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": "medium"},
            )
        except anthropic.APIStatusError as exc:
            logger.exception("Anthropic API error generating story")
            raise StoryGenerationFailedError(
                "The story generator is temporarily unavailable. Please try again."
            ) from exc
        except anthropic.APIConnectionError as exc:
            logger.exception("Could not reach the Anthropic API")
            raise StoryGenerationFailedError(
                "Could not reach the story generator. Please try again."
            ) from exc

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise StoryGenerationFailedError("The story generator returned an empty response.")

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
        )
