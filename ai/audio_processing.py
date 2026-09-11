"""Reference-audio validation and preprocessing.

Pipeline for an uploaded/recorded clip:

    raw bytes
      -> magic-byte container sniff        (never trust the filename)
      -> decode to mono float32 @ target SR (ffmpeg, soundfile fallback)
      -> duration validation
      -> leading/trailing silence trim
      -> peak normalisation to -1 dBFS
      -> write 16-bit PCM WAV

Why this shape:

* **ffmpeg** is the only dependency that reliably decodes what browsers
  actually produce. ``MediaRecorder`` emits WebM/Opus in Chrome & Firefox and
  MP4/AAC in Safari; ``soundfile``/libsndfile cannot read either. ffmpeg also
  does high-quality resampling, so we do not need librosa/resampy here.
* **soundfile + numpy** handle the WAV round-trip and the DSP. They are already
  transitive dependencies of the model, so they are free.
* We deliberately do *not* apply denoising or EQ: Chatterbox clones the timbre
  it is given, and aggressive cleanup measurably hurts speaker similarity.

Target sample rate: Chatterbox generates at **24 kHz** (``S3GEN_SR``) and
internally resamples the reference to 16 kHz for the speech tokenizer and
speaker encoder. Storing the reference at 24 kHz is lossless with respect to
what the model consumes.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 24_000
PEAK_TARGET_DBFS = -1.0
SILENCE_THRESHOLD_DBFS = -45.0
_TRIM_FRAME = 1024


class AudioValidationError(ValueError):
    """Raised for audio the API should reject with HTTP 400/422."""


@dataclass(frozen=True)
class AudioInfo:
    """Result of preprocessing one clip."""

    path: Path
    sample_rate: int
    duration_seconds: float
    channels_in: int
    container: str
    peak_dbfs: float
    trimmed_seconds: float


# --------------------------------------------------------------------------
# Container sniffing
# --------------------------------------------------------------------------

#: Extensions we advertise in the UI. The extension is a *hint* only.
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".opus", ".flac", ".aac"}

_MAGIC_NUMBERS: tuple[tuple[bytes, int, str], ...] = (
    (b"RIFF", 0, "wav"),  # also checked for b"WAVE" at offset 8
    (b"fLaC", 0, "flac"),
    (b"OggS", 0, "ogg"),
    (b"\x1a\x45\xdf\xa3", 0, "webm"),  # EBML -> WebM / Matroska
    (b"ID3", 0, "mp3"),
    (b"ftyp", 4, "mp4"),  # m4a / mp4 / aac-in-mp4
)


def sniff_container(data: bytes) -> str:
    """Identify the container from magic bytes.

    Returns a short container name, or ``"unknown"``.  Never raises.
    """
    if len(data) < 12:
        return "unknown"
    for magic, offset, name in _MAGIC_NUMBERS:
        if data[offset : offset + len(magic)] == magic:
            if name == "wav" and data[8:12] != b"WAVE":
                continue
            return name
    # Bare MPEG audio frame sync (MP3 without an ID3 tag).
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    # ADTS AAC
    if data[0] == 0xFF and (data[1] & 0xF6) == 0xF0:
        return "aac"
    return "unknown"


def assert_supported_container(data: bytes, *, declared_name: str | None = None) -> str:
    """Validate the payload by content, not by extension.

    ``declared_name`` is only used to improve the error message.
    """
    container = sniff_container(data)
    if container == "unknown":
        hint = f" (filename: {declared_name})" if declared_name else ""
        raise AudioValidationError(
            "Unrecognised audio format"
            f"{hint}. Supported: WAV, MP3, M4A/MP4, WebM, OGG/Opus, FLAC, AAC."
        )
    return container


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _decode_with_ffmpeg(src: Path, sample_rate: int) -> tuple[np.ndarray, int]:
    """Decode any container to mono float32 via ffmpeg."""
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-vn",  # drop any video/album-art stream
        "-map",
        "0:a:0",  # first audio stream only
        "-ac",
        "1",  # stereo -> mono
        "-ar",
        str(sample_rate),  # resample
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=False, timeout=120)
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - pathological input
        raise AudioValidationError("Audio decoding timed out.") from exc
    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        tail = detail[-1] if detail else "no output"
        raise AudioValidationError(f"Could not decode audio: {tail}")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy(), sample_rate


def _decode_with_soundfile(src: Path, sample_rate: int) -> tuple[np.ndarray, int]:
    """Fallback decoder for formats libsndfile understands (WAV/FLAC/OGG).

    Used when ffmpeg is unavailable (e.g. a lean CI image). Resampling is done
    with linear interpolation, which is adequate because this path only ever
    sees PCM WAV in practice.
    """
    try:
        audio, src_sr = sf.read(str(src), dtype="float32", always_2d=True)
    except Exception as exc:
        raise AudioValidationError(
            "Could not decode audio. ffmpeg is not installed and this format is "
            "not readable by libsndfile."
        ) from exc

    mono = audio.mean(axis=1)
    if src_sr != sample_rate:
        n_out = round(len(mono) * sample_rate / src_sr)
        if n_out <= 1:
            raise AudioValidationError("Audio is too short to process.")
        src_idx = np.linspace(0.0, len(mono) - 1, num=n_out, dtype=np.float64)
        mono = np.interp(src_idx, np.arange(len(mono), dtype=np.float64), mono).astype(np.float32)
    return mono, sample_rate


def decode_to_mono(
    src: str | Path, sample_rate: int = TARGET_SAMPLE_RATE
) -> tuple[np.ndarray, int]:
    """Decode ``src`` to a mono float32 array at ``sample_rate``."""
    src = Path(src)
    if ffmpeg_available():
        return _decode_with_ffmpeg(src, sample_rate)
    logger.warning("ffmpeg not found; falling back to libsndfile decoding")
    return _decode_with_soundfile(src, sample_rate)


# --------------------------------------------------------------------------
# DSP
# --------------------------------------------------------------------------


def peak_dbfs(audio: np.ndarray) -> float:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return float(20.0 * np.log10(peak)) if peak > 0 else float("-inf")


def trim_silence(
    audio: np.ndarray,
    *,
    threshold_dbfs: float = SILENCE_THRESHOLD_DBFS,
    frame: int = _TRIM_FRAME,
) -> np.ndarray:
    """Remove leading and trailing near-silence using frame-wise RMS."""
    if audio.size < frame:
        return audio
    n_frames = audio.size // frame
    frames = audio[: n_frames * frame].reshape(n_frames, frame)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
    with np.errstate(divide="ignore"):
        rms_db = 20.0 * np.log10(np.maximum(rms, 1e-12))
    voiced = np.flatnonzero(rms_db > threshold_dbfs)
    if voiced.size == 0:
        return audio  # all quiet: let duration/level validation report it
    start = int(voiced[0]) * frame
    end = min(audio.size, (int(voiced[-1]) + 1) * frame)
    return audio[start:end]


def normalize_peak(audio: np.ndarray, target_dbfs: float = PEAK_TARGET_DBFS) -> np.ndarray:
    """Scale so the loudest sample sits at ``target_dbfs``.

    Peak (not loudness) normalisation is intentional: it is transparent, it
    cannot pump or compress, and it preserves the dynamics the cloner keys on.
    """
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak <= 0:
        return audio
    target_amplitude = 10.0 ** (target_dbfs / 20.0)
    return (audio * (target_amplitude / peak)).astype(np.float32)


def write_wav(path: str | Path, audio: np.ndarray, sample_rate: int) -> Path:
    """Write mono 16-bit PCM WAV (universally playable in browsers)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(audio, -1.0, 1.0)
    sf.write(str(path), clipped, sample_rate, subtype="PCM_16", format="WAV")
    return path


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def preprocess_reference(
    data: bytes,
    dest: str | Path,
    *,
    filename: str | None = None,
    sample_rate: int = TARGET_SAMPLE_RATE,
    min_seconds: float = 3.0,
    max_seconds: float = 120.0,
    trim: bool = True,
    normalize: bool = True,
) -> AudioInfo:
    """Validate and normalise an uploaded reference clip, writing it to ``dest``.

    Raises :class:`AudioValidationError` for anything a user could plausibly
    send that we cannot or should not use.
    """
    container = assert_supported_container(data, declared_name=filename)

    with tempfile.TemporaryDirectory(prefix="vc-pre-") as tmp:
        raw_path = Path(tmp) / f"input.{container}"
        raw_path.write_bytes(data)
        audio, sr = decode_to_mono(raw_path, sample_rate)

    if audio.size == 0:
        raise AudioValidationError("The uploaded file contains no audio.")

    # Guard against NaN/Inf from malformed streams before any float maths.
    if not np.all(np.isfinite(audio)):
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

    raw_duration = audio.size / sr
    if raw_duration > max_seconds * 4:
        # Reject absurdly long input before spending time trimming it.
        raise AudioValidationError(
            f"Audio is {raw_duration:.0f}s long; the maximum is {max_seconds:.0f}s."
        )

    trimmed = trim_silence(audio) if trim else audio
    trimmed_seconds = (audio.size - trimmed.size) / sr
    duration = trimmed.size / sr

    if duration < min_seconds:
        raise AudioValidationError(
            f"Audio is only {duration:.1f}s of speech; at least {min_seconds:.0f}s is required. "
            "Record 10-30 seconds of continuous natural speech."
        )
    if duration > max_seconds:
        raise AudioValidationError(
            f"Audio is {duration:.0f}s long; the maximum is {max_seconds:.0f}s."
        )

    level = peak_dbfs(trimmed)
    if level < -50.0:
        raise AudioValidationError(
            "The recording is almost silent. Check your microphone and try again."
        )

    processed = normalize_peak(trimmed) if normalize else trimmed
    out = write_wav(dest, processed, sr)

    return AudioInfo(
        path=out,
        sample_rate=sr,
        duration_seconds=round(duration, 3),
        channels_in=1,
        container=container,
        peak_dbfs=round(level, 2),
        trimmed_seconds=round(trimmed_seconds, 3),
    )
