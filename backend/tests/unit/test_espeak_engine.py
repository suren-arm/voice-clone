"""ai.espeak_engine -- default-voice synthesis.

Skipped wholesale if espeak-ng is not on PATH (some CI/dev images may lack
it), same convention as ai.audio_processing's ffmpeg-dependent tests.
"""

import numpy as np
import pytest

from ai.espeak_engine import (
    DEFAULT_VOICES,
    EspeakError,
    default_voice_by_id,
    default_voices_for_language,
    espeak_available,
    synthesize_espeak,
)

pytestmark = pytest.mark.skipif(not espeak_available(), reason="espeak-ng is not installed")


def test_catalog_covers_every_app_language():
    """A built-in voice for each of en/hy/ru is what makes all three usable.

    The cloning model is English-only in production (turbo), so these are the
    voices that actually deliver Armenian and Russian.
    """
    from app.services.language import APP_LANGUAGE_CODES

    languages = {spec.language for spec in DEFAULT_VOICES}
    assert languages == set(APP_LANGUAGE_CODES) == {"en", "hy", "ru"}


def test_catalog_ids_are_unique():
    ids = [spec.id for spec in DEFAULT_VOICES]
    assert len(ids) == len(set(ids))


def test_default_voice_by_id_round_trips():
    for spec in DEFAULT_VOICES:
        assert default_voice_by_id(spec.id) is spec
    assert default_voice_by_id("not_a_real_id") is None


def test_default_voices_for_language_filters_correctly():
    hy_voices = default_voices_for_language("hy")
    assert hy_voices and all(spec.language == "hy" for spec in hy_voices)


def test_synthesize_english_produces_real_audio():
    audio, sr = synthesize_espeak("Hello, this is a test.", "en-us")
    assert sr > 0
    assert audio.dtype == np.float32
    assert audio.size > 0
    assert np.max(np.abs(audio)) > 0.01  # not silence


def test_synthesize_armenian_produces_real_audio():
    audio, _sr = synthesize_espeak("Բարև ձեզ։", "hy")
    assert audio.size > 0
    assert np.max(np.abs(audio)) > 0.01


def test_empty_text_raises():
    with pytest.raises(EspeakError):
        synthesize_espeak("   ", "en-us")


def test_unknown_voice_raises():
    with pytest.raises(EspeakError):
        synthesize_espeak("hello", "not-a-real-voice-code")
