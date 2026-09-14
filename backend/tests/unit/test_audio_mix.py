"""ai.audio_mix -- background-ambience mixing."""

import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from ai.audio_mix import AudioMixError, apply_speed, available_backgrounds, mix_with_background

_FFMPEG_MISSING = shutil.which("ffmpeg") is None


def test_mystical_ambience_asset_is_bundled_and_available():
    assert "mystical" in available_backgrounds()


def test_book_reader_ambience_presets_are_bundled_and_available():
    for name in ("calm", "forest", "bedtime"):
        assert name in available_backgrounds()


def test_unknown_background_name_raises(tmp_path: Path):
    narration = tmp_path / "narration.wav"
    narration.write_bytes(b"not-real-audio-but-path-must-exist-check-comes-first")
    with pytest.raises(AudioMixError, match="Unknown or missing background sound"):
        mix_with_background(
            narration, "nonexistent", volume_percent=15, out_path=tmp_path / "out.wav"
        )


def test_raises_clearly_when_ffmpeg_is_unavailable(tmp_path: Path, monkeypatch):
    import ai.audio_mix as audio_mix

    monkeypatch.setattr(audio_mix, "ffmpeg_available", lambda: False)
    narration = tmp_path / "narration.wav"
    narration.write_bytes(b"placeholder")
    with pytest.raises(AudioMixError, match="ffmpeg is not installed"):
        mix_with_background(narration, "mystical", volume_percent=15, out_path=tmp_path / "out.wav")


def _write_tone(path: Path, *, seconds: float = 2.0, sample_rate: int = 24_000) -> None:
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    tone = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(str(path), tone, sample_rate)


def test_apply_speed_is_a_noop_copy_at_1x(tmp_path: Path):
    narration = tmp_path / "narration.wav"
    _write_tone(narration)
    out = apply_speed(narration, 1.0, out_path=tmp_path / "out.wav")
    original, sr1 = sf.read(str(narration))
    result, sr2 = sf.read(str(out))
    assert sr1 == sr2
    assert len(original) == len(result)


@pytest.mark.skipif(_FFMPEG_MISSING, reason="requires ffmpeg")
def test_apply_speed_changes_duration(tmp_path: Path):
    narration = tmp_path / "narration.wav"
    _write_tone(narration, seconds=3.0)
    original_frames = sf.info(str(narration)).frames

    faster = apply_speed(narration, 1.5, out_path=tmp_path / "faster.wav")
    faster_frames = sf.info(str(faster)).frames
    # 1.5x speed should produce audio close to 1/1.5 the original length.
    assert faster_frames < original_frames
    assert abs(faster_frames / original_frames - 1 / 1.5) < 0.05

    slower = apply_speed(narration, 0.75, out_path=tmp_path / "slower.wav")
    slower_frames = sf.info(str(slower)).frames
    assert slower_frames > original_frames
    assert abs(slower_frames / original_frames - 1 / 0.75) < 0.05


def test_apply_speed_rejects_out_of_range_factor(tmp_path: Path):
    narration = tmp_path / "narration.wav"
    _write_tone(narration)
    with pytest.raises(AudioMixError, match="outside the supported"):
        apply_speed(narration, 3.0, out_path=tmp_path / "out.wav")


# -- narration clarity under background ------------------------------------
#
# The reported bug was "fairy-tale narration sounds echoey and muddy". These
# assert the three things that would each produce that symptom, on real
# ffmpeg output rather than by inspecting the filter string.


def _speech_tone(seconds: float = 3.0, sample_rate: int = 22_050) -> np.ndarray:
    """A voice-like signal: 130 Hz fundamental, harmonics up through ~4 kHz.

    The harmonic series has to reach the top of the clarity band, otherwise
    the bands this file asserts on have no baseline energy and a comparison
    against them divides by synthetic silence.
    """
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    harmonics = range(1, 31)  # 130 Hz .. 3.9 kHz
    tone = sum(np.sin(2 * np.pi * 130 * k * t) / k for k in harmonics)
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 3.5 * t)
    signal = tone * envelope
    return (0.5 * signal / np.abs(signal).max()).astype(np.float32)


def _band_rms(x: np.ndarray, sample_rate: int, lo: float, hi: float) -> float:
    spectrum = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / sample_rate)
    band = (freqs >= lo) & (freqs < hi)
    return float(np.sqrt(np.sum(np.abs(spectrum[band]) ** 2)) / len(x))


@pytest.mark.skipif(_FFMPEG_MISSING, reason="ffmpeg is not installed")
def test_background_does_not_mask_the_narration(tmp_path: Path):
    """The speech corridor must survive mixing essentially untouched.

    Before the fix this test's F0 band moved by a factor of ~1.85 with the
    mystical preset at its default level.
    """
    sample_rate = 22_050
    narration = _speech_tone(sample_rate=sample_rate)
    src = tmp_path / "narration.wav"
    sf.write(str(src), narration, sample_rate, subtype="PCM_16")

    out = tmp_path / "mixed.wav"
    mix_with_background(src, "mystical", volume_percent=15, out_path=out)
    mixed, mixed_rate = sf.read(str(out))
    mixed = np.asarray(mixed, dtype=float)

    for lo, hi in ((80, 300), (300, 1000), (1000, 4000)):
        before = _band_rms(np.asarray(narration, dtype=float), sample_rate, lo, hi)
        after = _band_rms(mixed, mixed_rate, lo, hi)
        if before <= 0:
            continue
        drift = abs(after - before) / before
        assert drift < 0.25, (
            f"{lo}-{hi} Hz moved {drift:.0%} after mixing -- the background is "
            f"competing with the narration in a band speech needs."
        )


@pytest.mark.skipif(_FFMPEG_MISSING, reason="ffmpeg is not installed")
def test_mixing_does_not_duplicate_the_narration(tmp_path: Path):
    """Exactly one narration stream in the output.

    The filter graph splits the narration so a copy can key the ducker. If
    that copy ever reached the mixer, the narration would be summed with
    itself -- which is precisely how you manufacture an echo.
    """
    sample_rate = 22_050
    narration = _speech_tone(sample_rate=sample_rate)
    src = tmp_path / "narration.wav"
    sf.write(str(src), narration, sample_rate, subtype="PCM_16")

    out = tmp_path / "mixed.wav"
    mix_with_background(src, "calm", volume_percent=0, out_path=out)
    mixed, _ = sf.read(str(out))
    mixed = np.asarray(mixed, dtype=float)

    # At volume 0 the background contributes nothing, so a correctly mixed
    # file is the narration itself -- not the narration plus a copy.
    n = min(len(mixed), len(narration))
    ratio = float(np.sqrt((mixed[:n] ** 2).mean()) / np.sqrt((narration[:n] ** 2).mean()))
    assert 0.9 < ratio < 1.15, (
        f"output is {ratio:.2f}x the narration's level with a silent background "
        f"-- a second copy of the narration is being summed in."
    )


@pytest.mark.skipif(_FFMPEG_MISSING, reason="ffmpeg is not installed")
def test_mixing_preserves_the_sample_rate_and_does_not_clip(tmp_path: Path):
    """The stored Generation.sample_rate must keep describing the file.

    espeak narration is 22.05 kHz and the ambience is 24 kHz; without an
    explicit rate the output silently came out at 24 kHz while the database
    row still said 22 050.
    """
    sample_rate = 22_050
    src = tmp_path / "narration.wav"
    sf.write(str(src), _speech_tone(sample_rate=sample_rate), sample_rate, subtype="PCM_16")

    out = tmp_path / "mixed.wav"
    mix_with_background(src, "mystical", volume_percent=100, out_path=out)
    mixed, mixed_rate = sf.read(str(out))

    assert mixed_rate == sample_rate
    assert np.abs(mixed).max() < 1.0, "mixed output is clipping"
