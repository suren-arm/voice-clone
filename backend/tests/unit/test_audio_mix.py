"""ai.audio_mix -- background-ambience mixing."""

from pathlib import Path

import pytest

from ai.audio_mix import AudioMixError, available_backgrounds, mix_with_background


def test_mystical_ambience_asset_is_bundled_and_available():
    assert "mystical" in available_backgrounds()


def test_unknown_background_name_raises(tmp_path: Path):
    narration = tmp_path / "narration.wav"
    narration.write_bytes(b"not-real-audio-but-path-must-exist-check-comes-first")
    with pytest.raises(AudioMixError, match="Unknown or missing background sound"):
        mix_with_background(narration, "forest", volume_percent=15, out_path=tmp_path / "out.wav")


def test_raises_clearly_when_ffmpeg_is_unavailable(tmp_path: Path, monkeypatch):
    import ai.audio_mix as audio_mix

    monkeypatch.setattr(audio_mix, "ffmpeg_available", lambda: False)
    narration = tmp_path / "narration.wav"
    narration.write_bytes(b"placeholder")
    with pytest.raises(AudioMixError, match="ffmpeg is not installed"):
        mix_with_background(
            narration, "mystical", volume_percent=15, out_path=tmp_path / "out.wav"
        )
