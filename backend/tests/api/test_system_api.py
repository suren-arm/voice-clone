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

    codes = [lang["code"] for lang in body["languages"]]
    # Exactly the three the product supports end to end, in UI order -- not
    # whatever the cloning model happens to list.
    assert codes == ["en", "hy", "ru"]


def test_every_app_language_reports_which_voices_can_speak_it(client):
    """The capability flags are what let the UI filter before generating.

    They must reflect the real engines: espeak-ng ships genuine hy/hyw and ru
    voices, while the cloning model in tests (mock, like production's turbo)
    is English-only.
    """
    languages = {
        lang["code"]: lang for lang in client.get("/api/v1/system/info").json()["languages"]
    }

    assert languages["hy"]["name"] == "Հայերեն"
    assert languages["ru"]["name"] == "Русский"
    assert languages["hy"]["englishName"] == "Armenian"

    for code in ("en", "hy", "ru"):
        assert languages[code]["supportsDefaultVoice"] is True, (
            f"{code} is offered but no built-in voice speaks it"
        )

    # Cloning capability is read off the engine, never assumed from the word
    # "multilingual" -- so assert it against what the engine actually claims.
    from ai.mock_engine import MOCK_LANGUAGES

    for code in ("en", "hy", "ru"):
        assert languages[code]["supportsClonedVoice"] is (code in MOCK_LANGUAGES)

    # And the one that holds for every variant: no cloning model this app can
    # load speaks Armenian, so it must never be advertised as cloneable.
    assert languages["hy"]["supportsClonedVoice"] is False


def test_no_language_is_offered_that_nothing_can_speak(client):
    from app.services.language import APP_LANGUAGES

    offered = {lang["code"] for lang in client.get("/api/v1/system/info").json()["languages"]}
    assert offered <= {lang.code for lang in APP_LANGUAGES}
    for lang in client.get("/api/v1/system/info").json()["languages"]:
        assert lang["supportsDefaultVoice"] or lang["supportsClonedVoice"]


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
