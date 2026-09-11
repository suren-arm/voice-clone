"""Rate limits are enforced end to end (they are off in every other test)."""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def limited_client(settings, monkeypatch):
    from fastapi.testclient import TestClient

    from ai.registry import reset_engine
    from app.api.deps import reset_rate_limiters
    from app.db.session import reset_db_state
    from app.main import create_app

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_speech_per_hour", 2)
    monkeypatch.setattr(settings, "rate_limit_voice_create_per_hour", 1)
    monkeypatch.setattr(settings, "rate_limit_global_per_minute", 1000)

    reset_db_state()
    reset_engine()
    reset_rate_limiters()
    with TestClient(create_app()) as client:
        yield client
    reset_engine()
    reset_db_state()
    reset_rate_limiters()


def test_voice_creation_is_rate_limited(limited_client, wav_bytes):
    payload = {"name": "V", "language": "en", "consent": "true"}
    files = {"audio": ("r.wav", wav_bytes, "audio/wav")}

    assert limited_client.post("/api/v1/voices", data=payload, files=files).status_code == 201
    blocked = limited_client.post("/api/v1/voices", data=payload, files=files)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1


def test_speech_generation_is_rate_limited(limited_client, wav_bytes):
    voice = limited_client.post(
        "/api/v1/voices",
        data={"name": "V", "language": "en", "consent": "true"},
        files={"audio": ("r.wav", wav_bytes, "audio/wav")},
    ).json()

    body = {"voiceId": voice["id"], "text": "Hello there.", "language": "en"}
    assert limited_client.post("/api/v1/speech", json=body).status_code == 201
    assert limited_client.post("/api/v1/speech", json=body).status_code == 201
    assert limited_client.post("/api/v1/speech", json=body).status_code == 429
