"""Default (non-cloned) voice catalog and generation through it.

espeak-ng-dependent: skipped wholesale if it is not on PATH, matching
tests/unit/test_espeak_engine.py's convention.
"""

import pytest

from ai.espeak_engine import espeak_available

pytestmark = pytest.mark.skipif(not espeak_available(), reason="espeak-ng is not installed")


def test_default_voices_are_listed(client):
    body = client.get("/api/v1/voices/defaults").json()
    assert len(body) == 4
    languages = {v["language"] for v in body}
    assert languages == {"en", "hy"}
    assert all(v["engine"] == "espeak-ng" for v in body)
    assert all(v["source"] == "system" for v in body)


def test_default_voices_do_not_count_against_the_voice_quota(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_voices", 1)
    # The quota is for the user's *own* voices; the 4 bootstrapped default
    # voices must not consume it, or nobody could ever create their first
    # cloned voice on a fresh deployment.
    response = client.post(
        "/api/v1/voices",
        data={"name": "My Voice", "language": "en", "consent": "true", "source": "record"},
        files={"audio": ("r.wav", _make_wav(), "audio/wav")},
    )
    assert response.status_code == 201


def test_default_voices_are_excluded_from_my_voices_listing(client):
    body = client.get("/api/v1/voices").json()
    assert body["meta"]["total"] == 0
    assert body["items"] == []


def test_generate_speech_with_english_default_voice(client):
    defaults = client.get("/api/v1/voices/defaults").json()
    voice = next(v for v in defaults if v["language"] == "en")
    response = client.post(
        "/api/v1/speech",
        json={"voiceId": voice["id"], "text": "Hello from the default voice.", "language": "en"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["engine"] == "espeak-ng"
    assert body["watermarked"] is False
    assert body["durationSeconds"] > 0


def test_generate_speech_with_armenian_default_voice_speaks_native_armenian(client):
    """Unlike the cloned-voice path, this is *not* the transliteration bridge:
    espeak-ng speaks Armenian script directly, so no experimental flag."""
    defaults = client.get("/api/v1/voices/defaults").json()
    voice = next(v for v in defaults if v["language"] == "hy")
    response = client.post(
        "/api/v1/speech",
        json={"voiceId": voice["id"], "text": "Բարև ձեզ։ Սա փորձարկում է։", "language": "hy"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["engine"] == "espeak-ng"
    assert body["experimental"] is False
    assert body["language"] == "hy"


def test_long_text_is_chunked_and_concatenated_for_a_default_voice(client):
    defaults = client.get("/api/v1/voices/defaults").json()
    voice = next(v for v in defaults if v["language"] == "en")
    long_text = "This is a short sentence about a fairy tale adventure. " * 20
    response = client.post(
        "/api/v1/speech",
        json={"voiceId": voice["id"], "text": long_text, "language": "en"},
    )
    assert response.status_code == 201
    assert response.json()["durationSeconds"] > 10


def test_background_sound_reports_unavailable_without_ffmpeg_gracefully(client, monkeypatch):
    # Patched where it is *used*: speech_service imports the name directly
    # (`from ai.audio_mix import ... ffmpeg_available ...`), so patching
    # `ai.audio_mix.ffmpeg_available` would leave that already-bound copy
    # untouched and this test would silently pass for the wrong reason
    # whenever ffmpeg happens to be genuinely absent from the test host.
    import app.services.speech_service as speech_service

    monkeypatch.setattr(speech_service, "ffmpeg_available", lambda: False)
    defaults = client.get("/api/v1/voices/defaults").json()
    voice = next(v for v in defaults if v["language"] == "en")
    response = client.post(
        "/api/v1/speech",
        json={
            "voiceId": voice["id"],
            "text": "Hello with background.",
            "language": "en",
            "backgroundSound": "mystical",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["backgroundApplied"] is False
    assert "ffmpeg" in body["backgroundNotice"]


def _make_wav() -> bytes:
    import io

    import numpy as np
    import soundfile as sf

    sr = 24_000
    t = np.arange(int(8.0 * sr), dtype=np.float32) / sr
    audio = (0.5 * np.sin(2 * np.pi * 145.0 * t)).astype(np.float32)
    buffer = io.BytesIO()
    sf.write(buffer, audio, sr, subtype="PCM_16", format="WAV")
    return buffer.getvalue()
