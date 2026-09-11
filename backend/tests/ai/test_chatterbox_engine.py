"""Real-model tests.

These download multi-gigabyte weights and need a GPU to finish quickly, so they
are marked ``ai`` and deselected by default. Run them deliberately:

    pytest -m ai tests/ai

Everything else in the suite uses the mock engine, which is why CI never
touches a model.
"""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.ai

chatterbox = pytest.importorskip("chatterbox", reason="chatterbox-tts is not installed")


@pytest.fixture(scope="module")
def engine():
    from ai.chatterbox_engine import ChatterboxEngine

    instance = ChatterboxEngine(variant="multilingual", device="auto", t3_model="v3")
    instance.load()
    yield instance
    instance.unload()


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    """A real reference clip.

    Tone-based audio is enough to exercise the plumbing; speaker similarity is
    judged by ear, not by assertion.
    """
    from ai.audio_processing import write_wav

    sr = 24_000
    t = np.arange(sr * 12, dtype=np.float32) / sr
    signal = sum(
        gain * np.sin(2 * np.pi * 130 * harmonic * t)
        for harmonic, gain in ((1, 1.0), (2, 0.5), (3, 0.25), (4, 0.12))
    )
    signal *= 0.6 + 0.4 * np.sin(2 * np.pi * 3.2 * t)
    path = tmp_path_factory.mktemp("ai") / "reference.wav"
    write_wav(path, (0.5 * signal / np.max(np.abs(signal))).astype(np.float32), sr)
    return path


def test_engine_metadata_matches_the_verified_upstream_contract(engine):
    info = engine.info()
    assert info.sample_rate == 24_000
    assert info.watermarked is True
    assert len(info.languages) == 23
    assert "hy" not in info.languages, "Armenian is not natively supported (see docs/ARMENIAN.md)"


def test_create_voice_produces_a_loadable_conditioning_cache(engine, reference, tmp_path):
    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "voice")
    assert profile.conditioning_path.is_file()
    assert profile.conditioning_path.stat().st_size > 0


def test_synthesize_english(engine, reference, tmp_path):
    from ai.engine import SynthesisRequest

    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "voice")
    result = engine.synthesize(
        SynthesisRequest(profile=profile, text="Hello, this is a test.", language="en", seed=1234)
    )
    assert result.sample_rate == 24_000
    assert result.duration_seconds > 0.5
    assert result.watermarked is True
    assert np.max(np.abs(result.audio)) <= 1.0


def test_watermark_is_detectable(engine, reference, tmp_path):
    """Provenance claim, verified rather than assumed."""
    perth = pytest.importorskip("perth", reason="resemble-perth is not installed")

    from ai.engine import SynthesisRequest

    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "voice")
    result = engine.synthesize(
        SynthesisRequest(profile=profile, text="This audio is watermarked.", language="en")
    )
    watermarker = perth.PerthImplicitWatermarker()
    assert watermarker.get_watermark(result.audio, sample_rate=result.sample_rate) == 1.0


def test_unsupported_language_raises(engine, reference, tmp_path):
    from ai.engine import SynthesisRequest, UnsupportedLanguageError

    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "voice")
    with pytest.raises(UnsupportedLanguageError):
        engine.synthesize(SynthesisRequest(profile=profile, text="Բարև", language="hy"))


def test_real_time_factor_is_reported(engine, reference, tmp_path):
    from ai.engine import SynthesisRequest

    profile = engine.create_voice("voice_abc123def456", reference, workdir=tmp_path / "voice")
    result = engine.synthesize(
        SynthesisRequest(
            profile=profile,
            text="The quick brown fox jumps over the lazy dog, twice in a row.",
            language="en",
        )
    )
    print(f"\nRTF={result.real_time_factor:.3f} on {engine.device}")
    assert result.real_time_factor > 0
