"""Audio validation and preprocessing."""

import io

import numpy as np
import pytest
import soundfile as sf

from ai.audio_processing import (
    AudioValidationError,
    normalize_peak,
    peak_dbfs,
    preprocess_reference,
    sniff_container,
    trim_silence,
)
from tests.conftest import make_wav_bytes


def test_sniff_wav():
    assert sniff_container(make_wav_bytes(seconds=1)) == "wav"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"\x1a\x45\xdf\xa3" + b"\x00" * 16, "webm"),
        (b"OggS" + b"\x00" * 16, "ogg"),
        (b"fLaC" + b"\x00" * 16, "flac"),
        (b"ID3\x04\x00\x00" + b"\x00" * 16, "mp3"),
        (b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 8, "mp4"),
        (b"\xff\xfb\x90\x64" + b"\x00" * 16, "mp3"),
        (b"this is not audio at all, honestly", "unknown"),
        (b"", "unknown"),
    ],
)
def test_sniff_container(payload, expected):
    assert sniff_container(payload) == expected


def test_wav_extension_on_non_wav_content_is_rejected():
    """The extension is a hint; the bytes decide."""
    with pytest.raises(AudioValidationError, match="Unrecognised audio format"):
        preprocess_reference(b"totally not audio" * 100, "/tmp/x.wav", filename="innocent.wav")


def test_preprocess_writes_mono_wav_at_target_rate(tmp_path):
    info = preprocess_reference(make_wav_bytes(seconds=8), tmp_path / "ref.wav")
    assert info.path.is_file()
    audio, sr = sf.read(info.path, always_2d=True)
    assert sr == 24_000
    assert audio.shape[1] == 1
    assert 7.5 < info.duration_seconds <= 8.0


def test_preprocess_normalises_peak(tmp_path):
    quiet = make_wav_bytes(seconds=6)
    audio, sr = sf.read(io.BytesIO(quiet), dtype="float32")
    buffer = io.BytesIO()
    sf.write(buffer, audio * 0.05, sr, subtype="PCM_16", format="WAV")

    info = preprocess_reference(buffer.getvalue(), tmp_path / "ref.wav")
    written, _ = sf.read(info.path, dtype="float32")
    assert peak_dbfs(written) == pytest.approx(-1.0, abs=0.3)


def test_preprocess_rejects_too_short(tmp_path, short_wav_bytes):
    with pytest.raises(AudioValidationError, match="at least"):
        preprocess_reference(short_wav_bytes, tmp_path / "ref.wav", min_seconds=3)


def test_preprocess_rejects_too_long(tmp_path):
    with pytest.raises(AudioValidationError, match="maximum"):
        preprocess_reference(make_wav_bytes(seconds=40), tmp_path / "ref.wav", max_seconds=30)


def test_preprocess_rejects_silence(tmp_path, silent_wav_bytes):
    with pytest.raises(AudioValidationError):
        preprocess_reference(silent_wav_bytes, tmp_path / "ref.wav")


def test_preprocess_rejects_empty_upload(tmp_path):
    with pytest.raises(AudioValidationError):
        preprocess_reference(b"", tmp_path / "ref.wav")


def test_trim_silence_removes_leading_and_trailing():
    sr = 24_000
    silence = np.zeros(sr, dtype=np.float32)
    speech = (0.5 * np.sin(2 * np.pi * 200 * np.arange(sr * 2) / sr)).astype(np.float32)
    trimmed = trim_silence(np.concatenate([silence, speech, silence]))
    assert 1.8 * sr <= trimmed.size <= 2.2 * sr


def test_trim_silence_keeps_all_quiet_audio_intact():
    quiet = np.full(48_000, 1e-6, dtype=np.float32)
    assert trim_silence(quiet).size == quiet.size


def test_normalize_peak_is_a_noop_on_digital_silence():
    silence = np.zeros(1000, dtype=np.float32)
    assert np.array_equal(normalize_peak(silence), silence)
