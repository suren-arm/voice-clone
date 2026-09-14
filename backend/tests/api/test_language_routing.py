"""Every feature, in every language the product claims to support.

The bug this guards against was not a missing dropdown entry. The language
catalogue was derived from the cloning engine alone, so on production
(``CHATTERBOX_VARIANT=turbo``, English-only) it collapsed to one entry and
Armenian disappeared from Text to Speech -- while espeak-ng was sitting
right there with working hy/hyw voices. These assert the round trip, not
the list.
"""

from __future__ import annotations

import pytest

from ai.espeak_engine import espeak_available

pytestmark = pytest.mark.skipif(not espeak_available(), reason="espeak-ng is not installed")

#: Real text in each script, so a broken encoding path cannot pass.
SAMPLE_TEXT = {
    "en": "Hello. This is an English text-to-speech test.",
    "hy": "Բարև։ Սա հայերեն խոսքի փորձարկում է։",
    "ru": "Привет. Это проверка русского синтеза речи.",
}


def _default_voice(client, language: str) -> dict:
    voices = client.get("/api/v1/voices/defaults").json()
    voice = next((v for v in voices if v["language"] == language), None)
    assert voice is not None, f"no built-in voice for '{language}'"
    return voice


@pytest.mark.parametrize("language", ["en", "hy", "ru"])
def test_text_to_speech_works_in_every_app_language(client, language: str):
    voice = _default_voice(client, language)
    response = client.post(
        "/api/v1/speech",
        json={"voiceId": voice["id"], "text": SAMPLE_TEXT[language], "language": language},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["language"] == language
    assert body["durationSeconds"] > 0, "synthesis produced no audio"
    # The text round-trips intact -- no mangled Unicode, no transliteration.
    assert body["text"] == SAMPLE_TEXT[language]
    assert client.get(body["audioUrl"]).status_code == 200


@pytest.mark.parametrize("language", ["en", "hy", "ru"])
def test_every_app_language_has_a_usable_default_voice(client, language: str):
    voice = _default_voice(client, language)
    assert voice["engine"] == "espeak-ng"
    assert voice["source"] == "system"


def test_a_default_voice_refuses_a_language_it_does_not_speak(client):
    """espeak's Armenian voice cannot read Russian; say so before generating."""
    armenian = _default_voice(client, "hy")
    response = client.post(
        "/api/v1/speech",
        json={"voiceId": armenian["id"], "text": SAMPLE_TEXT["ru"], "language": "ru"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["message"] == (
        "This voice cannot speak Русский. Please choose another voice."
    )


@pytest.mark.parametrize("language", ["en", "hy", "ru"])
def test_narration_with_background_still_succeeds_in_every_language(client, language: str):
    voice = _default_voice(client, language)
    response = client.post(
        "/api/v1/speech",
        json={
            "voiceId": voice["id"],
            "text": SAMPLE_TEXT[language],
            "language": language,
            "backgroundSound": "mystical",
            "backgroundVolume": 15,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["durationSeconds"] > 0


# -- fairy tale ------------------------------------------------------------


@pytest.mark.parametrize("language", ["en", "hy", "ru"])
def test_story_prompt_asks_for_native_generation_not_translation(language: str):
    """Direct generation in the target language, never draft-then-translate."""
    from app.schemas.story import StoryRequest
    from app.services.story_prompt import StoryPromptBuilder

    prompt = StoryPromptBuilder.build(
        StoryRequest(
            language=language,
            characters="Կարապետ և Ռուզաննա" if language == "hy" else "Karen and Anna",
            idea="A magical world of giant animals",
            age_group="6-8",
            length="short",
            tone="magical",
        )
    )
    assert "natively" in prompt.system

    if language == "hy":
        assert "Armenian script" in prompt.system
        assert "do not draft it in English and translate" in prompt.system
    elif language == "ru":
        assert "Cyrillic script" in prompt.system
        assert "do not transliterate Russian into Latin letters" in prompt.system


def test_story_request_rejects_a_language_the_product_does_not_support():
    import pydantic

    from app.schemas.story import StoryRequest

    with pytest.raises(pydantic.ValidationError):
        StoryRequest(
            language="de",
            characters="Hans",
            idea="A forest",
            age_group="6-8",
            length="short",
            tone="magical",
        )


@pytest.mark.parametrize("language", ["en", "hy", "ru"])
def test_a_generated_story_can_be_narrated_in_its_own_language(client, language: str):
    """The fairy tale's narration step is the same endpoint as Text to Speech.

    This is the architectural requirement -- one narration pipeline, not a
    separate FairyTaleTTS -- so proving the story text narrates through
    POST /speech in each language proves both features at once.
    """
    voice = _default_voice(client, language)
    story_text = {
        "en": "Once upon a time, two children discovered a magical forest.",
        "hy": "Մի անգամ երկու երեխաներ հայտնվեցին կախարդական անտառում։",
        "ru": "Однажды двое детей оказались в волшебном лесу.",
    }[language]

    response = client.post(
        "/api/v1/speech",
        json={"voiceId": voice["id"], "text": story_text, "language": language},
    )
    assert response.status_code == 201, response.text
    assert response.json()["text"] == story_text
