"""Engine contract, exercised through the mock implementation.

These assertions are the contract every real engine must also satisfy, which is
why they are written against the interface rather than against Chatterbox.
"""

import numpy as np
import pytest

from ai.audio_processing import write_wav
from ai.engine import EngineError, SynthesisRequest, UnsupportedLanguageError
from ai.mock_engine import MockEngine
from ai.registry import available_engines, get_engine, reset_engine


@pytest.fixture
def reference(tmp_path):
    sr = 24_000
    t = np.arange(sr * 6) / sr
    path = tmp_path / "ref.wav"
    write_wav(path, (0.4 * np.sin(2 * np.pi * 140 * t)).astype(np.float32), sr)
    return path


@pytest.fixture
def engine():
    return MockEngine()


def test_info_works_without_loading(engine):
    info = engine.info()
    assert not engine.is_loaded
    assert info.sample_rate == 24_000
    assert "en" in info.languages


def test_create_voice_persists_conditioning(engine, reference, tmp_path):
    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "v")
    assert profile.conditioning_path is not None
    assert profile.conditioning_path.is_file()
    assert profile.engine == engine.name


def test_conditioning_is_deterministic_per_reference(engine, reference, tmp_path):
    a = engine.create_voice("voice_aaaaaaaaaaaa", reference, workdir=tmp_path / "a")
    b = engine.create_voice("voice_bbbbbbbbbbbb", reference, workdir=tmp_path / "b")
    assert a.metadata["base_hz"] == b.metadata["base_hz"]


def test_synthesize_returns_audio_and_telemetry(engine, reference, tmp_path):
    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "v")
    result = engine.synthesize(
        SynthesisRequest(profile=profile, text="Hello from my cloned voice.", language="en")
    )
    assert result.audio.dtype == np.float32
    assert result.audio.ndim == 1
    assert result.sample_rate == 24_000
    assert result.duration_seconds > 0
    assert np.max(np.abs(result.audio)) <= 1.0
    assert result.real_time_factor >= 0


def test_synthesize_rejects_empty_text(engine, reference, tmp_path):
    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "v")
    with pytest.raises(EngineError):
        engine.synthesize(SynthesisRequest(profile=profile, text="   ", language="en"))


def test_synthesize_rejects_unknown_language(engine, reference, tmp_path):
    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "v")
    with pytest.raises(UnsupportedLanguageError):
        engine.synthesize(SynthesisRequest(profile=profile, text="hi", language="xx"))


def test_missing_reference_is_a_clear_error(engine, reference, tmp_path):
    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "v")
    profile.conditioning_path.unlink()
    reference.unlink()
    with pytest.raises(EngineError, match="must be recreated"):
        engine.synthesize(SynthesisRequest(profile=profile, text="hi", language="en"))


def test_registry_returns_a_singleton():
    reset_engine()
    try:
        assert get_engine("mock") is get_engine("mock")
    finally:
        reset_engine()


def test_registry_rejects_unknown_engine():
    reset_engine()
    with pytest.raises(ValueError, match="Unknown engine"):
        get_engine("does-not-exist")


def test_available_engines_lists_both():
    assert set(available_engines()) == {"chatterbox", "mock"}
