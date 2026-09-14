"""Fairy-tale generation in each app language, with the model stubbed out.

What this can and cannot prove: it exercises the whole pipeline -- request
validation, prompt construction, provider dispatch, response parsing, title
splitting, word counting and the narration-ready text -- for English,
Armenian and Russian. It cannot judge whether a real model writes *good*
Armenian; that needs a live provider key and a native reader.

Stubbing is the point, not a shortcut: these must not depend on a vendor
being reachable, or on someone's quota.
"""

from __future__ import annotations

import pytest

from app.schemas.story import StoryRequest
from app.services.ai_providers.base import AiTextProvider, StoryPrompt
from app.services.ai_providers.registry import AiProviderRegistry
from app.services.story_service import StoryService

#: Realistic output per language -- the exact test cases from the brief.
STORY_FIXTURES: dict[str, tuple[str, str, str]] = {
    "en": (
        "Karen and Anna",
        "An adventure in a magical forest",
        "The Blue Door\n\nOnce upon a time, two children discovered a magical forest.",
    ),
    "hy": (
        "Կարապետ և Ռուզաննա",
        "Հսկայական կենդանիների կախարդական աշխարհ",
        "Կախարդական աշխարհը\n\nՄի անգամ Կարապետն ու Ռուզաննան հայտնվեցին "
        "մի կախարդական աշխարհում, ուր ապրում էին հսկայական կենդանիներ։",
    ),
    "ru": (
        "Карен и Анна",
        "Приключение в волшебном лесу",
        "Синяя дверь\n\nОднажды двое детей оказались в волшебном лесу, "
        "где деревья умели разговаривать.",
    ),
}


class StubProvider(AiTextProvider):
    """Returns canned text and records the prompt it was handed."""

    id = "stub"
    display_name = "Stub"
    kind = "local"

    def __init__(self, text: str) -> None:
        self._text = text
        self.seen: StoryPrompt | None = None

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: StoryPrompt) -> str:
        self.seen = prompt
        return self._text


def _service(text: str) -> tuple[StoryService, StubProvider]:
    provider = StubProvider(text)
    registry = AiProviderRegistry(
        providers={provider.id: provider},
        preferred_provider=None,
        auto_prefer_free=False,
    )
    return StoryService(registry=registry), provider


@pytest.mark.parametrize("language", ["en", "hy", "ru"])
def test_a_story_round_trips_intact_in_every_app_language(language: str):
    characters, idea, text = STORY_FIXTURES[language]
    service, provider = _service(text)

    response = service.generate(
        StoryRequest(
            language=language,
            characters=characters,
            idea=idea,
            age_group="6-8",
            length="short",
            tone="magical",
            provider="stub",
        )
    )

    assert response.language == language
    assert response.word_count > 0
    # Title and body split correctly, and the script survives byte for byte.
    expected_title, _, expected_body = text.partition("\n")
    assert response.title == expected_title
    assert response.text == expected_body.strip()
    assert response.text in text

    # The characters the user typed reach the model unaltered -- no
    # transliteration, no anglicising.
    assert provider.seen is not None
    assert characters in provider.seen.user


@pytest.mark.parametrize("language", ["hy", "ru"])
def test_the_model_is_told_to_write_natively_not_translate(language: str):
    characters, idea, text = STORY_FIXTURES[language]
    service, provider = _service(text)
    service.generate(
        StoryRequest(
            language=language,
            characters=characters,
            idea=idea,
            age_group="6-8",
            length="short",
            tone="magical",
            provider="stub",
        )
    )
    assert provider.seen is not None
    system = provider.seen.system
    assert "natively" in system
    assert "do not draft it in English and translate" in system
    assert "do not mix English words or sentences into the story" in system


def test_a_story_with_no_title_line_still_produces_a_body():
    """A model that ignores the title instruction must not yield empty text."""
    service, _ = _service("Однажды двое детей оказались в волшебном лесу.")
    response = service.generate(
        StoryRequest(
            language="ru",
            characters="Карен и Анна",
            idea="Лес",
            age_group="6-8",
            length="short",
            tone="magical",
            provider="stub",
        )
    )
    assert response.title == "Untitled"
    assert "Однажды" in response.text
