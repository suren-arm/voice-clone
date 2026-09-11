"""``/api/v1/voices`` contract tests."""

import pytest

from tests.conftest import make_wav_bytes


def _create(client, **overrides):
    data = {"name": "My Voice", "language": "en", "consent": "true", "source": "record"}
    data.update({k: v for k, v in overrides.items() if k != "audio"})
    files = {"audio": overrides.get("audio", ("reference.wav", make_wav_bytes(), "audio/wav"))}
    return client.post("/api/v1/voices", data=data, files=files)


def test_create_voice_returns_201_and_profile(client):
    response = _create(client)
    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("voice_")
    assert body["name"] == "My Voice"
    assert body["language"] == "en"
    assert body["consentGiven"] is True
    assert body["generationCount"] == 0
    assert body["sampleUrl"].endswith("/sample")
    assert 7.0 < body["referenceDurationSeconds"] <= 8.0


def test_create_voice_trims_and_sanitises_the_name(client):
    body = _create(client, name="  Sur\x00en's  Voice  ").json()
    assert body["name"] == "Surens Voice" or body["name"] == "Suren's Voice"


def test_create_voice_requires_consent(client):
    response = _create(client, consent="false")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "consent_required"
    assert "statement" in response.json()["error"]["details"]


def test_create_voice_rejects_missing_audio(client):
    response = client.post(
        "/api/v1/voices", data={"name": "X", "language": "en", "consent": "true"}
    )
    assert response.status_code == 422


def test_create_voice_rejects_unsupported_format(client):
    response = _create(client, audio=("clip.wav", b"definitely not audio" * 50, "audio/wav"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_audio"


def test_create_voice_rejects_too_short_audio(client, short_wav_bytes):
    response = _create(client, audio=("short.wav", short_wav_bytes, "audio/wav"))
    assert response.status_code == 422
    assert "at least" in response.json()["error"]["message"]


def test_create_voice_rejects_oversized_upload(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    response = _create(client, audio=("big.wav", make_wav_bytes(seconds=8), "audio/wav"))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_create_voice_rejects_unknown_language(client):
    response = _create(client, language="xx")
    assert response.status_code == 422


def test_create_voice_enforces_the_voice_quota(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "max_voices", 1)
    assert _create(client).status_code == 201
    response = _create(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "quota_exceeded"


def test_list_voices_is_paginated_and_newest_first(client):
    ids = [_create(client, name=f"Voice {i}").json()["id"] for i in range(3)]
    body = client.get("/api/v1/voices?limit=2&offset=0").json()
    assert body["meta"] == {"total": 3, "limit": 2, "offset": 0}
    assert len(body["items"]) == 2
    assert body["items"][0]["id"] == ids[-1]


def test_get_voice(client, created_voice):
    body = client.get(f"/api/v1/voices/{created_voice['id']}").json()
    assert body["id"] == created_voice["id"]


@pytest.mark.parametrize(
    "voice_id", ["voice_zzzzzzzzzzzz", "not-an-id", "..", "voice_../../etc/passwd"]
)
def test_get_unknown_or_malicious_voice_id_is_404(client, voice_id):
    assert client.get(f"/api/v1/voices/{voice_id}").status_code == 404


def test_get_voice_sample_returns_wav(client, created_voice):
    response = client.get(created_voice["sampleUrl"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_delete_voice_removes_row_and_files(client, created_voice, settings):
    voice_id = created_voice["id"]
    voice_dir = settings.voices_dir / voice_id
    assert voice_dir.is_dir()

    response = client.delete(f"/api/v1/voices/{voice_id}")
    assert response.status_code == 200
    assert response.json() == {"id": voice_id, "deleted": True}
    assert not voice_dir.exists()
    assert client.get(f"/api/v1/voices/{voice_id}").status_code == 404


def test_delete_unknown_voice_is_404(client):
    assert client.delete("/api/v1/voices/voice_zzzzzzzzzzzz").status_code == 404
