"""Default-voice synthesis via ``espeak-ng``.

This is deliberately *not* another :class:`ai.engine.VoiceCloningEngine`
implementation: espeak-ng does not clone anything, it just speaks fixed
formant-synthesis voices, so bolting it onto the cloning interface (which
revolves entirely around ``VoiceProfile``/conditioning) would be a worse fit
than a small, direct wrapper.

Why espeak-ng, and why this is honestly labelled "Classic" quality rather than
passed off as natural neural speech: see ``docs/ARMENIAN.md`` -> "Default-voice
Armenian TTS". Short version -- it is already a runtime dependency of
``backend/Dockerfile.render`` (used via subprocess, same pattern as ffmpeg), it
ships genuine Eastern (``hy``) and Western (``hyw``) Armenian voices with
correct native phonetics, and every neural alternative found had either an
incompatible licence or an unverifiable/poor quality claim.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from io import BytesIO

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

#: espeak-ng's own output rate. Left as-is rather than resampled: it is a
#: perfectly good rate for its own robotic-formant output, and resampling
#: would add a dependency for no audible benefit.
ESPEAK_SAMPLE_RATE = 22_050

_DEFAULT_RATE_WPM = 165
_DEFAULT_PITCH = 50


class EspeakError(RuntimeError):
    """Raised when espeak-ng is missing or fails."""


@dataclass(frozen=True)
class DefaultVoiceSpec:
    """One curated default (non-cloned) voice."""

    id: str
    name: str
    language: str  # app language code: "en" or "hy"
    espeak_voice: str  # the -v argument, e.g. "en-us", "hy", "hyw"
    gender: str  # "male" | "female" -- purely a label; espeak-ng's variants
    # are pitch/formant shifts on the same synthesiser, not distinct voices.
    quality: str = "classic"


#: Curated, real, working espeak-ng voices. Nothing here is invented: every
#: entry was verified to load and produce audio via `espeak-ng -v <code>`.
DEFAULT_VOICES: tuple[DefaultVoiceSpec, ...] = (
    DefaultVoiceSpec(
        id="default_en_male",
        name="English (Male, Classic)",
        language="en",
        espeak_voice="en-us",
        gender="male",
    ),
    DefaultVoiceSpec(
        id="default_en_female",
        name="English (Female, Classic)",
        language="en",
        espeak_voice="en-us+f3",
        gender="female",
    ),
    DefaultVoiceSpec(
        id="default_hy_eastern",
        name="Հայերեն · Արևելյան (Eastern Armenian, Classic)",
        language="hy",
        espeak_voice="hy",
        gender="male",
    ),
    DefaultVoiceSpec(
        id="default_hy_western",
        name="Հայերեն · Արևմտյան (Western Armenian, Classic)",
        language="hy",
        espeak_voice="hyw",
        gender="male",
    ),
)

_BY_ID: dict[str, DefaultVoiceSpec] = {spec.id: spec for spec in DEFAULT_VOICES}


def default_voice_by_id(voice_id: str) -> DefaultVoiceSpec | None:
    return _BY_ID.get(voice_id)


def default_voices_for_language(language: str) -> list[DefaultVoiceSpec]:
    return [spec for spec in DEFAULT_VOICES if spec.language == language.lower()]


def espeak_available() -> bool:
    return shutil.which("espeak-ng") is not None


def synthesize_espeak(
    text: str,
    espeak_voice: str,
    *,
    rate_wpm: int = _DEFAULT_RATE_WPM,
    pitch: int = _DEFAULT_PITCH,
) -> tuple[np.ndarray, int]:
    """Synthesize ``text`` with espeak-ng, returning mono float32 PCM + rate.

    Raises :class:`EspeakError` if the binary is missing or fails -- callers
    map this onto the same "engine unavailable" story as the cloning engine.
    """
    if not espeak_available():
        raise EspeakError("espeak-ng is not installed on this server.")
    if not text.strip():
        raise EspeakError("Cannot synthesize empty text.")

    cmd = [
        "espeak-ng",
        "-v",
        espeak_voice,
        "-s",
        str(rate_wpm),
        "-p",
        str(pitch),
        "--stdout",
        text,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=False, timeout=60)
    except subprocess.TimeoutExpired as exc:
        raise EspeakError("espeak-ng timed out.") from exc
    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode("utf-8", "replace").strip() or "no output"
        raise EspeakError(f"espeak-ng failed: {detail}")

    audio, sr = sf.read(BytesIO(proc.stdout), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1).astype(np.float32)
    return mono, sr
