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
        mix_with_background(
            narration, "mystical", volume_percent=15, out_path=tmp_path / "out.wav"
        )


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
