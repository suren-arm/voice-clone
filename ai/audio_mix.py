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

import soundfile as sf

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
#:
#: Lowered from 0.55 when the ambience tracks were found to be masking the
#: narration: 0.55 was a ceiling at which even a well-behaved track competes
#: with speech, and it existed because it was the only safeguard. It is no
#: longer the only one -- the tracks now stay out of the speech band (see
#: scripts/generate_ambience.py) and the mix ducks them under narration -- so
#: the ceiling can be what it should always have been.
_MAX_BACKGROUND_GAIN = 0.25


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

    # Match the narration's own rate. Without this, ffmpeg resolves the rate
    # mismatch between narration and ambience however it likes -- a 22.05 kHz
    # espeak narration silently came out at 24 kHz, disagreeing with the
    # sample_rate this generation is recorded as having.
    narration_rate = sf.info(str(narration_path)).samplerate

    # The filter graph, and why each stage is here:
    #
    #   [0:a] narration --asplit--> [narr]  (the one and only audio in the mix)
    #                           \-> [key]   (control signal, never mixed in)
    #   [1:a] ambience  --volume--> [bg] --sidechaincompress(keyed by [key])-->
    #                                        [duck] --\
    #                                                  amix --> [aout]
    #                                        [narr] --/
    #
    # sidechaincompress pulls the ambience down while the narrator is
    # speaking and lets it back up in the gaps, which is what keeps speech
    # intelligible regardless of what the ambience track contains. Note the
    # asplit: [key] only ever steers the compressor. If it reached amix the
    # narration would be summed with a copy of itself -- the classic way to
    # manufacture exactly the echo this function is meant to avoid.
    duck = (
        "sidechaincompress="
        "threshold=0.02:"  # duck as soon as there is speech at all
        "ratio=6:"
        "attack=20:"  # ms -- fast enough to catch a word's onset
        "release=400:"  # ms -- slow enough not to pump between words
        "makeup=1"
    )
    filter_complex = (
        f"[0:a]aformat=sample_fmts=fltp:sample_rates={narration_rate}:channel_layouts=mono,"
        "asplit=2[narr][key];"
        f"[1:a]aformat=sample_fmts=fltp:sample_rates={narration_rate}:channel_layouts=mono,"
        f"volume={gain:.4f}[bg];"
        f"[bg][key]{duck}[duck];"
        "[narr][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mixed];"
        # Mixing two signals can push peaks past full scale. Limit rather than
        # attenuate everything: the narration keeps its level and only the
        # overshoot is caught.
        "[mixed]alimiter=limit=0.97:level=disabled[aout]"
    )

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
        filter_complex,
        "-map",
        "[aout]",
        "-ac",
        "1",
        "-ar",
        str(narration_rate),
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
