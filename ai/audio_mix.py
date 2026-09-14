"""Narration + background-ambience mixing via ffmpeg.

Mirrors the subprocess pattern already used in :mod:`ai.audio_processing`
for decoding -- ffmpeg is the one dependency that reliably handles looping,
trimming and mixing without pulling in a separate DSP library.

Bundled ambience tracks live in ``backend/app/assets/ambience/`` and are
entirely self-generated (see ``scripts/generate_ambience.py``) -- no
third-party audio, so no licence question to track.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "assets" / "ambience"

#: Background options the API accepts. "none" is handled by callers before
#: they ever reach this module. All tracks are self-generated (see
#: scripts/generate_ambience.py) -- no licence question for any of them.
BACKGROUND_SOUNDS: dict[str, Path] = {
    "mystical": _ASSETS_DIR / "mystical.wav",
    "calm": _ASSETS_DIR / "calm.wav",
    "forest": _ASSETS_DIR / "forest.wav",
    "bedtime": _ASSETS_DIR / "bedtime.wav",
}

#: However high the caller sets the volume slider, the background is capped
#: at this fraction of the narration's level -- "the narration must stay
#: louder and clearer than the background" is a product requirement, not a
#: suggestion, so it is enforced here rather than trusted to the frontend.
_MAX_BACKGROUND_GAIN = 0.55


class AudioMixError(RuntimeError):
    """Raised when mixing fails; callers fall back to the unmixed narration."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def available_backgrounds() -> list[str]:
    return sorted(name for name, path in BACKGROUND_SOUNDS.items() if path.is_file())


def mix_with_background(
    narration_path: str | Path,
    background: str,
    *,
    volume_percent: int,
    out_path: str | Path,
) -> Path:
    """Mix ``narration_path`` with a looped ``background`` track.

    ``volume_percent`` (0-100) is the caller-facing slider value; the actual
    gain applied is clamped to :data:`_MAX_BACKGROUND_GAIN` of full scale so
    the narration always reads clearly over it. Writes the result to
    ``out_path`` (may be the same file as ``narration_path``, via a temp file)
    and returns it.
    """
    track_path = BACKGROUND_SOUNDS.get(background)
    if track_path is None or not track_path.is_file():
        raise AudioMixError(f"Unknown or missing background sound '{background}'.")
    if not ffmpeg_available():
        raise AudioMixError("ffmpeg is not installed on this server.")

    narration_path = Path(narration_path)
    out_path = Path(out_path)
    gain = min(max(volume_percent, 0), 100) / 100.0 * _MAX_BACKGROUND_GAIN

    # Write to a sibling temp file first: out_path may equal narration_path,
    # and ffmpeg cannot safely read and write the same file at once.
    tmp_out = out_path.with_suffix(out_path.suffix + ".mixing.wav")

    cmd = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(narration_path),
        "-stream_loop",
        "-1",
        "-i",
        str(track_path),
        "-filter_complex",
        (
            f"[1:a]volume={gain:.4f}[bg];"
            "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        ),
        "-map",
        "[aout]",
        "-ac",
        "1",
        str(tmp_out),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=False, timeout=120)
    except subprocess.TimeoutExpired as exc:
        tmp_out.unlink(missing_ok=True)
        raise AudioMixError("Audio mixing timed out.") from exc
    if proc.returncode != 0 or not tmp_out.is_file():
        tmp_out.unlink(missing_ok=True)
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        tail = detail[-1] if detail else "no output"
        raise AudioMixError(f"Could not mix background audio: {tail}")

    tmp_out.replace(out_path)
    return out_path


#: ffmpeg's `atempo` filter is documented as reliable (no pitch shift, no
#: artefacts) only within 0.5-2.0 in a single filter instance -- comfortably
#: covers the reading-speed range this app actually exposes (0.75x-1.5x), so
#: there is no need to chain multiple atempo stages.
_ATEMPO_MIN = 0.5
_ATEMPO_MAX = 2.0


def apply_speed(narration_path: str | Path, factor: float, *, out_path: str | Path) -> Path:
    """Time-stretch narration by ``factor`` (no pitch shift) via ffmpeg's atempo.

    A no-op (straight copy) at ``factor == 1.0`` so the common case never
    touches audio quality. Applied to the narration alone, *before* any
    background mix -- see callers -- so ambience always loops to match the
    already-adjusted narration length rather than being time-stretched itself.
    """
    narration_path = Path(narration_path)
    out_path = Path(out_path)
    if factor == 1.0:
        if narration_path != out_path:
            shutil.copyfile(narration_path, out_path)
        return out_path
    if not (_ATEMPO_MIN <= factor <= _ATEMPO_MAX):
        raise AudioMixError(
            f"Speed factor {factor} is outside the supported {_ATEMPO_MIN}-{_ATEMPO_MAX} range."
        )
    if not ffmpeg_available():
        raise AudioMixError("ffmpeg is not installed on this server.")

    tmp_out = out_path.with_suffix(out_path.suffix + ".speed.wav")
    cmd = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(narration_path),
        "-filter:a",
        f"atempo={factor:.4f}",
        str(tmp_out),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=False, timeout=120)
    except subprocess.TimeoutExpired as exc:
        tmp_out.unlink(missing_ok=True)
        raise AudioMixError("Speed adjustment timed out.") from exc
    if proc.returncode != 0 or not tmp_out.is_file():
        tmp_out.unlink(missing_ok=True)
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        tail = detail[-1] if detail else "no output"
        raise AudioMixError(f"Could not adjust narration speed: {tail}")

    tmp_out.replace(out_path)
    return out_path
