"""The bundled ambience must not mask narration.

These lock in the fix for a real, reported bug: fairy-tale narration sounded
"unclear, echoing, reverberated, muddy". It was none of those things
literally -- no reverb filter, no duplicated stream, no chunk overlap. The
``mystical`` and ``calm`` tracks were tonal sine pads at 110-220 Hz, i.e.
sitting exactly on a narrator's fundamental, carrying 100% of their energy
inside the speech corridor and reaching 0.85x the narration's own energy
there at default settings. That is textbook masking, and a continuous tonal
drone under a voice is perceived as room reverb.

Two independent guards, so neither alone has to be perfect:
  1. the tracks themselves stay out of the corridor (here), and
  2. the mix ducks them under speech (test_audio_mix.py).
"""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from ai.audio_mix import BACKGROUND_SOUNDS

#: Kept in step with scripts/generate_ambience.py, which enforces the same
#: limit at generation time. Imported rather than duplicated would be nicer,
#: but scripts/ is not an importable package.
SPEECH_F0_HZ = 150.0
SPEECH_CLARITY_TOP_HZ = 5000.0
MAX_SPEECH_BAND_ENERGY = 0.15


def _speech_band_energy(audio: np.ndarray, sample_rate: int) -> float:
    spectrum = np.abs(np.fft.rfft(audio)) ** 2
    freqs = np.fft.rfftfreq(len(audio), 1 / sample_rate)
    corridor = (freqs >= SPEECH_F0_HZ) & (freqs < SPEECH_CLARITY_TOP_HZ)
    total = spectrum.sum()
    return float(spectrum[corridor].sum() / total) if total else 0.0


@pytest.mark.parametrize("name", sorted(BACKGROUND_SOUNDS))
def test_ambience_track_stays_out_of_the_speech_corridor(name: str):
    path = BACKGROUND_SOUNDS[name]
    if not path.is_file():
        pytest.skip(f"ambience asset '{name}' is not bundled in this checkout")

    audio, sample_rate = sf.read(str(path))
    share = _speech_band_energy(np.asarray(audio, dtype=float), sample_rate)

    assert share <= MAX_SPEECH_BAND_ENERGY, (
        f"'{name}' puts {share:.1%} of its energy in the "
        f"{SPEECH_F0_HZ:.0f}-{SPEECH_CLARITY_TOP_HZ:.0f} Hz speech corridor "
        f"(limit {MAX_SPEECH_BAND_ENERGY:.0%}). Under narration this masks the "
        f"voice and is heard as muddiness/echo. Regenerate with "
        f"scripts/generate_ambience.py."
    )


@pytest.mark.parametrize("name", sorted(BACKGROUND_SOUNDS))
def test_ambience_track_loops_without_a_click(name: str):
    """Seam continuity: the wrap-around must not pop under a quiet story."""
    path = BACKGROUND_SOUNDS[name]
    if not path.is_file():
        pytest.skip(f"ambience asset '{name}' is not bundled in this checkout")

    audio, _ = sf.read(str(path))
    audio = np.asarray(audio, dtype=float)
    # The step across the loop point must be no larger than the track's own
    # typical sample-to-sample movement -- otherwise it is an audible click.
    seam_step = abs(float(audio[0]) - float(audio[-1]))
    typical_step = float(np.abs(np.diff(audio)).max())
    assert seam_step <= max(typical_step, 1e-4), (
        f"'{name}' jumps {seam_step:.5f} across its loop point "
        f"(largest ordinary step is {typical_step:.5f}) -- that is a click."
    )
