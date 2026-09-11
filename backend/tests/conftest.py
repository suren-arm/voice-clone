"""Shared fixtures.

Every test runs against the **mock engine** and a throwaway SQLite file, so the
whole suite finishes in seconds and needs no GPU, no network and no model
weights. Tests that genuinely need the real model live in ``tests/ai`` behind
the ``ai`` marker.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND.parent
for path in (str(_BACKEND), str(_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolated settings pointing at a temp storage tree and DB."""
    storage = tmp_path / "storage"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("VOICE_ENGINE", "mock")
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_ARMENIAN", "true")

    from app.core.config import get_settings

    get_settings.cache_clear()
    resolved = get_settings()
    resolved.ensure_directories()
    yield resolved
    get_settings.cache_clear()


@pytest.fixture
def app(settings):
    from ai.registry import reset_engine
    from app.api.deps import reset_rate_limiters
    from app.db.session import reset_db_state
    from app.main import create_app

    reset_db_state()
    reset_engine()
    reset_rate_limiters()

    application = create_app()
    yield application

    reset_engine()
    reset_db_state()
    reset_rate_limiters()


@pytest.fixture
def client(app) -> Iterator:
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


# -- audio fixtures ---------------------------------------------------------


def make_wav_bytes(seconds: float = 8.0, sample_rate: int = 24_000, freq: float = 145.0) -> bytes:
    """A speech-ish WAV: a voiced tone with a syllable-rate envelope."""
    import io

    import soundfile as sf

    t = np.arange(int(seconds * sample_rate), dtype=np.float32) / sample_rate
    tone = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 2 * t)
    envelope = 0.6 + 0.4 * np.sin(2 * np.pi * 3.5 * t)
    audio = (0.5 * tone * envelope).astype(np.float32)

    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, subtype="PCM_16", format="WAV")
    return buffer.getvalue()


@pytest.fixture
def wav_bytes() -> bytes:
    return make_wav_bytes()


@pytest.fixture
def short_wav_bytes() -> bytes:
    """Below the 3 s minimum."""
    return make_wav_bytes(seconds=1.0)


@pytest.fixture
def silent_wav_bytes() -> bytes:
    import io

    import soundfile as sf

    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(24_000 * 8, dtype=np.float32), 24_000, subtype="PCM_16", format="WAV")
    return buffer.getvalue()


@pytest.fixture
def created_voice(client, wav_bytes) -> dict:
    response = client.post(
        "/api/v1/voices",
        data={"name": "Test Voice", "language": "en", "consent": "true", "source": "record"},
        files={"audio": ("reference.wav", wav_bytes, "audio/wav")},
    )
    assert response.status_code == 201, response.text
    return response.json()
