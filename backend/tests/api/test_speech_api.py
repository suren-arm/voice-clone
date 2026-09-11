"""``/api/v1/speech`` and ``/api/v1/generations`` contract tests."""

import pytest


def _generate(client, voice_id, **overrides):
    payload = {"voiceId": voice_id, "text": "Hello from my cloned voice.", "language": "en"}
    payload.update(overrides)
    return client.post("/api/v1/speech", json=payload)


def test_generate_speech_returns_a_generation_resource(client, created_voice):
    response = _generate(client, created_voice["id"])
    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("gen_")
    assert body["voiceId"] == created_voice["id"]
    assert body["audioUrl"].endswith("/audio")
    assert body["durationSeconds"] > 0
    assert body["realTimeFactor"] >= 0
    assert body["experimental"] is False
    assert body["language"] == "en"


def test_generate_increments_the_voice_usage_counter(client, created_voice):
    _generate(client, created_voice["id"])
    _generate(client, created_voice["id"])
    body = client.get(f"/api/v1/voices/{created_voice['id']}").json()
    assert body["generationCount"] == 2
    assert body["lastUsedAt"] is not None


def test_generated_audio_is_downloadable_wav(client, created_voice):
    url = _generate(client, created_voice["id"]).json()["audioUrl"]
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"
    assert response.headers["accept-ranges"] == "bytes"
    assert "inline" in response.headers["content-disposition"]


def test_download_flag_sets_attachment_disposition(client, created_voice):
    url = _generate(client, created_voice["id"]).json()["audioUrl"]
    response = client.get(f"{url}?download=true")
    assert "attachment" in response.headers["content-disposition"]


def test_audio_supports_byte_ranges(client, created_voice):
    url = _generate(client, created_voice["id"]).json()["audioUrl"]
    full = client.get(url).content

    partial = client.get(url, headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206
    assert len(partial.content) == 100
    assert partial.content == full[:100]
    assert partial.headers["content-range"] == f"bytes 0-99/{len(full)}"

    suffix = client.get(url, headers={"Range": "bytes=-50"})
    assert suffix.status_code == 206
    assert suffix.content == full[-50:]

    beyond = client.get(url, headers={"Range": f"bytes={len(full) + 10}-"})
    assert beyond.status_code == 416


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_empty_text_is_rejected(client, created_voice, text):
    assert _generate(client, created_voice["id"], text=text).status_code == 422


def test_text_over_the_configured_limit_is_rejected(client, created_voice, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_text_chars", 20)
    response = _generate(client, created_voice["id"], text="x" * 100)
    assert response.status_code == 422
    assert response.json()["error"]["details"]["maxChars"] == 20


def test_text_over_the_absolute_ceiling_is_rejected_by_schema(client, created_voice):
    response = _generate(client, created_voice["id"], text="x" * 6000)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_voice_is_404(client):
    response = _generate(client, "voice_zzzzzzzzzzzz")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "voice_not_found"


def test_malformed_voice_id_is_404_not_500(client):
    assert _generate(client, "../../etc/passwd").status_code == 404


def test_unsupported_language_is_422(client, created_voice):
    response = _generate(client, created_voice["id"], language="xx")
    assert response.json()["error"]["code"] == "unsupported_language"


@pytest.mark.parametrize(
    ("field", "value"),
    [("exaggeration", 5.0), ("cfgWeight", -1), ("temperature", 0.0), ("seed", -3)],
)
def test_out_of_range_controls_are_rejected(client, created_voice, field, value):
    assert _generate(client, created_voice["id"], **{field: value}).status_code == 422


def test_generations_can_be_listed_and_filtered(client, created_voice, wav_bytes):
    other = client.post(
        "/api/v1/voices",
        data={"name": "Other", "language": "en", "consent": "true"},
        files={"audio": ("r.wav", wav_bytes, "audio/wav")},
    ).json()

    _generate(client, created_voice["id"])
    _generate(client, created_voice["id"])
    _generate(client, other["id"])

    assert client.get("/api/v1/generations").json()["meta"]["total"] == 3
    filtered = client.get(f"/api/v1/generations?voiceId={created_voice['id']}").json()
    assert filtered["meta"]["total"] == 2
    assert all(item["voiceId"] == created_voice["id"] for item in filtered["items"])


def test_get_and_delete_a_generation(client, created_voice, settings):
    generation = _generate(client, created_voice["id"]).json()
    path = settings.generated_dir / f"{generation['id']}.wav"
    assert path.is_file()

    assert client.get(f"/api/v1/generations/{generation['id']}").status_code == 200
    assert client.delete(f"/api/v1/generations/{generation['id']}").status_code == 200
    assert not path.exists()
    assert client.get(f"/api/v1/generations/{generation['id']}").status_code == 404


def test_deleting_a_voice_cascades_to_its_generations(client, created_voice, settings):
    generation = _generate(client, created_voice["id"]).json()
    audio_path = settings.generated_dir / f"{generation['id']}.wav"
    assert audio_path.is_file()

    client.delete(f"/api/v1/voices/{created_voice['id']}")

    assert client.get("/api/v1/generations").json()["meta"]["total"] == 0
    assert not audio_path.exists(), "generated audio must not survive voice deletion"
