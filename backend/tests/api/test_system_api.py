"""Capability discovery and error-envelope shape."""


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "version" in body


def test_system_info_describes_engine_languages_and_limits(client):
    body = client.get("/api/v1/system/info").json()
    assert body["engine"]["name"] == "mock"
    assert body["engine"]["sampleRate"] == 24_000
    assert body["limits"]["maxTextChars"] > 0
    assert body["limits"]["requireConsent"] is True
    assert "wav" in body["acceptedAudioFormats"]

    codes = {lang["code"] for lang in body["languages"]}
    assert {"en", "ru", "de"} <= codes


def test_armenian_is_advertised_as_experimental(client):
    languages = client.get("/api/v1/system/info").json()["languages"]
    armenian = next(lang for lang in languages if lang["code"] == "hy")
    assert armenian["experimental"] is True
    assert armenian["native"] is False
    assert "not natively supported" in armenian["note"]


def test_armenian_can_be_switched_off(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "enable_experimental_armenian", False)
    languages = client.get("/api/v1/system/info").json()["languages"]
    assert all(lang["code"] != "hy" for lang in languages)


def test_errors_use_the_standard_envelope(client):
    body = client.get("/api/v1/voices/voice_zzzzzzzzzzzz").json()
    assert set(body) == {"error"}
    assert set(body["error"]) >= {"code", "message"}


def test_openapi_schema_is_generated(client):
    spec = client.get("/openapi.json").json()
    assert "/api/v1/voices" in spec["paths"]
    assert "/api/v1/speech" in spec["paths"]
