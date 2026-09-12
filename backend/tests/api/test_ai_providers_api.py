"""``GET /api/v1/ai/providers`` -- capability discovery, never leaks keys."""

from __future__ import annotations


def test_lists_all_four_providers_with_availability(client):
    body = client.get("/api/v1/ai/providers").json()
    ids = {p["id"] for p in body["providers"]}
    assert ids == {"openai", "gemini", "anthropic", "ollama"}
    # None configured in the test environment.
    assert all(p["available"] is False for p in body["providers"])
    assert body["autoResolvesTo"] is None


def test_never_exposes_a_key_or_secret_value(client):
    body = client.get("/api/v1/ai/providers").json()
    raw = str(body)
    assert "sk-" not in raw
    assert "API_KEY" not in raw.upper()


def test_configured_provider_is_marked_available(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-key")
    body = client.get("/api/v1/ai/providers").json()
    openai_entry = next(p for p in body["providers"] if p["id"] == "openai")
    assert openai_entry["available"] is True
    assert body["autoResolvesTo"] == "openai"


def test_kinds_match_expected_classification(client):
    body = client.get("/api/v1/ai/providers").json()
    kinds = {p["id"]: p["kind"] for p in body["providers"]}
    assert kinds["openai"] == "paid"
    assert kinds["anthropic"] == "paid"
    assert kinds["gemini"] == "free-tier"
    assert kinds["ollama"] == "local"
