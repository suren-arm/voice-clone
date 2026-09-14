"""``POST /api/v1/stories/generate`` -- request validation and wiring.

Success-path generation itself is covered against a mocked Anthropic client
in tests/unit/test_story_service.py; these tests exercise the HTTP layer
(validation, the no-API-key 503, rate limiting) without ever calling the
real Anthropic API.
"""


def _story_payload(**overrides):
    payload = {
        "language": "en",
        "characters": "A rabbit and a fox",
        "idea": "they become unlikely friends",
        "ageGroup": "6-8",
        "length": "short",
        "tone": "magical",
    }
    payload.update(overrides)
    return payload


def test_story_generation_without_api_key_is_503(client):
    response = client.post("/api/v1/stories/generate", json=_story_payload())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "story_service_unavailable"
    # The message must be useful and provider-neutral, not the old
    # single-provider "ANTHROPIC_API_KEY is not set" leak.
    assert "provider" in response.json()["error"]["message"].lower()


def test_explicit_unconfigured_provider_is_503_not_a_silent_fallback(client):
    response = client.post("/api/v1/stories/generate", json=_story_payload(provider="openai"))
    assert response.status_code == 503
    assert "OpenAI" in response.json()["error"]["message"]


def test_unknown_provider_id_is_503(client):
    response = client.post(
        "/api/v1/stories/generate", json=_story_payload(provider="not-a-real-provider")
    )
    assert response.status_code == 503


def test_story_request_accepts_armenian_language(client, settings, monkeypatch):
    # Still 503 (no key configured in tests), but must pass request validation
    # for "hy" -- confirms Armenian is a first-class accepted story language.
    response = client.post("/api/v1/stories/generate", json=_story_payload(language="hy"))
    assert response.status_code == 503  # not 422 -- "hy" itself is valid


def test_unknown_language_is_422(client):
    response = client.post("/api/v1/stories/generate", json=_story_payload(language="fr"))
    assert response.status_code == 422


def test_missing_characters_is_422(client):
    payload = _story_payload()
    del payload["characters"]
    assert client.post("/api/v1/stories/generate", json=payload).status_code == 422


def test_blank_idea_is_422(client):
    assert (
        client.post("/api/v1/stories/generate", json=_story_payload(idea="   ")).status_code == 422
    )


def test_unknown_length_or_tone_is_422(client):
    assert (
        client.post("/api/v1/stories/generate", json=_story_payload(length="epic")).status_code
        == 422
    )
    assert (
        client.post("/api/v1/stories/generate", json=_story_payload(tone="scary")).status_code
        == 422
    )


def test_story_generation_is_rate_limited(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_story_per_hour", 2)

    from app.api.deps import reset_rate_limiters

    reset_rate_limiters()
    for _ in range(2):
        client.post("/api/v1/stories/generate", json=_story_payload())
    response = client.post("/api/v1/stories/generate", json=_story_payload())
    assert response.status_code == 429
