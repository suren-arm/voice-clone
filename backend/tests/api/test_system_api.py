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
    assert body["limits"]["maxPdfBytes"] > 0
    assert body["limits"]["maxPdfPages"] > 0
    assert body["limits"]["maxBookNarrationChars"] > 0

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
    assert "/api/v1/books/upload" in spec["paths"]


def test_startup_does_not_construct_the_engine(client):
    """Booting must not import torch.

    ``ChatterboxEngine.__init__`` calls ``resolve_device()``, which imports
    torch -- ~45s on a cold page cache, which is exactly the state a freshly
    deployed container is in. Lifespan blocks the server from accepting any
    connection until it returns, so doing this at boot pushed the deploy
    health check past its timeout and the service never answered. The engine
    is created by the first request that actually needs it instead.
    """
    from ai.registry import current_engine

    assert current_engine() is None

    # /health is the probe a deploy waits on -- it must stay cheap.
    assert client.get("/health").json()["engineLoaded"] is False
    assert current_engine() is None


def test_health_reports_a_loaded_engine_created_outside_startup(client):
    """``engineLoaded`` must stay truthful now that boot no longer sets it.

    /health used to read ``app.state.engine``, which only lifespan assigned.
    With the engine created on first request, it reads the registry instead --
    so an engine loaded by a request is still reported.
    """
    from ai.registry import current_engine

    client.get("/api/v1/system/info")
    engine = current_engine()
    assert engine is not None
    assert client.get("/health").json()["engineLoaded"] is engine.is_loaded

    engine.load()
    assert client.get("/health").json()["engineLoaded"] is True
