"""End-to-end flow across API, services, storage, DB and engine.

Mirrors the user journey the product is built around:
record -> create voice -> enter text -> generate -> play -> download -> delete.
"""

import json

import pytest

pytestmark = pytest.mark.integration


def test_full_journey(client, settings, wav_bytes):
    # 1. Discover capabilities the way the frontend does.
    info = client.get("/api/v1/system/info").json()
    assert info["limits"]["requireConsent"] is True
    languages = {lang["code"] for lang in info["languages"]}

    # 2. Create a voice from a "recording".
    voice = client.post(
        "/api/v1/voices",
        data={"name": "Studio Voice", "language": "en", "consent": "true", "source": "record"},
        files={"audio": ("recording.webm", wav_bytes, "audio/webm")},
    ).json()

    # Storage is self-describing: metadata sits next to the audio.
    voice_dir = settings.voices_dir / voice["id"]
    metadata = json.loads((voice_dir / "metadata.json").read_text())
    assert metadata["consent"]["given"] is True
    assert metadata["name"] == "Studio Voice"
    assert (voice_dir / "reference.wav").is_file()
    assert list(voice_dir.glob("conds.*")), "conditioning cache should be persisted"

    # 3. Generate speech.
    generation = client.post(
        "/api/v1/speech",
        json={"voiceId": voice["id"], "text": "Hello. This is my cloned voice.", "language": "en"},
    ).json()

    # 4. Play it (range request, as a browser <audio> element does).
    head = client.get(generation["audioUrl"], headers={"Range": "bytes=0-1023"})
    assert head.status_code == 206

    # 5. Download it.
    download = client.get(f"{generation['audioUrl']}?download=true")
    assert download.content[:4] == b"RIFF"
    assert len(download.content) == generation["sizeBytes"]

    # 6. It shows up in history.
    history = client.get("/api/v1/generations").json()
    assert history["items"][0]["id"] == generation["id"]

    # 7. Deleting the voice removes everything derived from it.
    client.delete(f"/api/v1/voices/{voice['id']}")
    assert not voice_dir.exists()
    assert not (settings.generated_dir / f"{generation['id']}.wav").exists()
    assert client.get("/api/v1/generations").json()["meta"]["total"] == 0
    assert languages  # discovered above and used by the UI


def test_conditioning_cache_is_reused_across_generations(client, created_voice, settings):
    """Second and later generations must not re-read the reference clip."""
    voice_dir = settings.voices_dir / created_voice["id"]
    cache = next(voice_dir.glob("conds.*"))

    client.post(
        "/api/v1/speech",
        json={"voiceId": created_voice["id"], "text": "First.", "language": "en"},
    )
    # Remove the reference: if the cache were not used, this would fail.
    (voice_dir / "reference.wav").unlink()

    response = client.post(
        "/api/v1/speech",
        json={"voiceId": created_voice["id"], "text": "Second, from cache only.", "language": "en"},
    )
    assert response.status_code == 201, response.text
    assert cache.is_file()


def test_experimental_armenian_round_trip(client, created_voice):
    response = client.post(
        "/api/v1/speech",
        json={
            "voiceId": created_voice["id"],
            "text": "Բարև Ձեզ։ Իմ անունը Սուրեն է։",
            "language": "hy",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["experimental"] is True
    assert body["language"] == "hy"
    assert "not natively supported" in body["notice"]
    # The original Armenian text is what the user sees in their history.
    assert "Բարև" in body["text"]
    assert client.get(body["audioUrl"]).status_code == 200


def test_audit_trail_records_creation_generation_and_deletion(client, created_voice, app):
    from app.db.session import session_scope
    from app.repositories.audit_repo import AuditRepository

    client.post(
        "/api/v1/speech",
        json={"voiceId": created_voice["id"], "text": "Audited.", "language": "en"},
    )
    client.delete(f"/api/v1/voices/{created_voice['id']}")

    with session_scope() as session:
        events = [row.event for row in AuditRepository(session).list()]

    assert {"voice.created", "speech.generated", "voice.deleted"} <= set(events)


def test_audit_events_survive_voice_deletion(client, created_voice):
    from app.db.session import session_scope
    from app.repositories.audit_repo import AuditRepository

    voice_id = created_voice["id"]
    client.delete(f"/api/v1/voices/{voice_id}")

    with session_scope() as session:
        rows = AuditRepository(session).list()

    assert any(row.subject_id == voice_id and row.event == "voice.created" for row in rows)


def test_actor_is_stored_hashed_not_in_the_clear(client, created_voice):
    from app.db.session import session_scope
    from app.repositories.audit_repo import AuditRepository

    with session_scope() as session:
        rows = AuditRepository(session).list()

    hashes = {row.actor_hash for row in rows if row.actor_hash}
    assert hashes
    assert all(len(value) == 32 and "." not in value for value in hashes)
