"""StoryPromptBuilder -- the one prompt every provider receives."""

from __future__ import annotations

from app.schemas.story import StoryRequest
from app.services.story_prompt import StoryPromptBuilder


def _request(**overrides) -> StoryRequest:
    payload = {
        "language": "en",
        "characters": "A rabbit and a fox",
        "idea": "they become unlikely friends",
        "ageGroup": "6-8",
        "length": "short",
        "tone": "magical",
    }
    payload.update(overrides)
    return StoryRequest.model_validate(payload)


def test_english_prompt_names_the_language_and_characters():
    prompt = StoryPromptBuilder.build(_request())
    assert "English" in prompt.system
    assert "A rabbit and a fox" in prompt.user
    assert "unlikely friends" in prompt.user


def test_armenian_prompt_carries_the_native_generation_instruction():
    prompt = StoryPromptBuilder.build(_request(language="hy"))
    assert "Armenian" in prompt.system
    assert "fluently in Armenian" in prompt.system
    assert "do not draft it in English" in prompt.system


def test_length_tiers_scale_the_token_budget():
    short = StoryPromptBuilder.build(_request(length="short"))
    medium = StoryPromptBuilder.build(_request(length="medium"))
    long_ = StoryPromptBuilder.build(_request(length="long"))
    assert short.max_tokens < medium.max_tokens < long_.max_tokens


def test_tone_and_age_group_appear_in_the_user_turn():
    prompt = StoryPromptBuilder.build(_request(tone="bedtime", ageGroup="3-5"))
    assert "bedtime" in prompt.user
    assert "3-5" in prompt.user
