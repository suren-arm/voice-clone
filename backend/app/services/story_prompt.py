"""Builds the one, provider-agnostic prompt every AI provider receives.

Centralized so no single provider implementation carries its own idea of
what a "fairy tale" prompt looks like -- every provider gets the exact same
:class:`~app.services.ai_providers.base.StoryPrompt`, and a change to how
stories are framed (tone guidance, age-appropriateness, the Armenian
native-generation instruction) takes effect for every provider at once.
"""

from __future__ import annotations

from app.schemas.story import StoryRequest
from app.services.ai_providers.base import StoryPrompt

_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hy": "Armenian (Հայերեն, Eastern Armenian as spoken in Armenia)",
    "ru": "Russian (Русский, as spoken in Russia)",
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

_BASE_SYSTEM_INSTRUCTION = (
    "You are a warm, imaginative children's fairy-tale author. Write a complete, "
    "original, wholesome fairy tale meant to be read aloud. Respect the requested "
    "language, characters, theme, age group, length and tone exactly. Avoid any "
    "inappropriate, frightening, or violent content. Use natural, engaging "
    "storytelling, and include a positive conclusion or gentle lesson where it "
    "fits naturally -- never forced or preachy. Output plain narration text "
    "only: no markdown, no stage directions, no headings other than the title. "
    "Start with a single short title line, then a blank line, then the story."
)

#: Generating directly in the target language beats drafting in English and
#: translating: translation flattens idiom and, in practice, leaks English
#: sentences into the output. Each non-English language gets an explicit
#: instruction saying so, naming its own script.
_NATIVE_SCRIPT_INSTRUCTION: dict[str, str] = {
    "hy": (
        " Write the ENTIRE story directly and fluently in Armenian, using Armenian "
        "script throughout -- do not draft it in English and translate, and do not "
        "mix English words or sentences into the story. Do not unnecessarily "
        "translate or anglicize the character names the user supplied."
    ),
    "ru": (
        " Write the ENTIRE story directly and fluently in Russian, using Cyrillic "
        "script throughout -- do not draft it in English and translate, do not "
        "transliterate Russian into Latin letters, and do not mix English words or "
        "sentences into the story. Do not unnecessarily translate or anglicize the "
        "character names the user supplied."
    ),
}


class StoryPromptBuilder:
    """Turns a validated :class:`StoryRequest` into a :class:`StoryPrompt`."""

    @staticmethod
    def build(request: StoryRequest) -> StoryPrompt:
        language_name = _LANGUAGE_NAMES[request.language]
        target_words, max_tokens = _LENGTH_SPEC[request.length]
        tone = _TONE_GUIDANCE[request.tone]
        age = _AGE_GUIDANCE[request.age_group]

        system = _BASE_SYSTEM_INSTRUCTION + f" Write the ENTIRE story natively in {language_name}."
        native_instruction = _NATIVE_SCRIPT_INSTRUCTION.get(request.language)
        if native_instruction:
            system += native_instruction

        user = (
            f"Main characters: {request.characters}\n"
            f"Story idea: {request.idea}\n"
            f"Age group: {request.age_group} ({age})\n"
            f"Tone: {request.tone} -- {tone}\n"
            f"Target length: about {target_words} words."
        )

        return StoryPrompt(system=system, user=user, max_tokens=max_tokens)
