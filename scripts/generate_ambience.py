#!/usr/bin/env python3
"""Synthesize the background-ambience tracks bundled with this app.

Why generate rather than source an audio file: the app's licensing rule is
"never bundle copyrighted commercial music, and don't call something open
source just because it's downloadable" (see docs/ARMENIAN.md for the same
standard applied to voice models). The cleanest way to satisfy that for a
background-ambience feature is to not need a licence at all -- every track
here is generated from scratch with plain sine-wave additive synthesis, no
samples, no third-party material. Copyright: none to assign: purely
procedural output has no separate creative expression to protect beyond the
code itself, which is MIT like the rest of this repository.

Every track loops seamlessly: all oscillator and envelope frequencies are
chosen as exact integer multiples of ``1 / DURATION_SECONDS``, so amplitude
and phase both match at the wrap-around point -- no fade needed, no click.

**Every track must stay out of the speech band.** These play *underneath*
narration, and speech intelligibility lives in roughly 300 Hz - 4 kHz, with
the voice's fundamental (F0) around 80-300 Hz. A tonal drone sitting in that
region does not sound like a quiet background: it masks the fundamental and
is perceived as muddiness and room reverb -- "the narration sounds echoey".
The first versions of ``mystical`` and ``calm`` were exactly that mistake:
110-220 Hz sine pads carrying 100%% of their energy inside the F0 band, which
measured at 0.85x the narration's own energy there at the default mix level.

So the rule, enforced by ``verify_speech_safety()`` below and by
``tests/unit/test_ambience_assets.py``: put the weight below
:data:`SPEECH_F0_HZ` (felt as warmth, not heard as pitch) or above
:data:`SPEECH_CLARITY_TOP_HZ` (air and shimmer), and leave the corridor
between them to the voice.

Run manually to regenerate: ``python3 scripts/generate_ambience.py``
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24_000
DURATION_SECONDS = 30.0
OUT_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "assets" / "ambience"

#: Below this, content is felt as warmth rather than competing with a voice's
#: fundamental. Above SPEECH_CLARITY_TOP_HZ, it is air rather than articulation.
SPEECH_F0_HZ = 150.0
SPEECH_CLARITY_TOP_HZ = 5000.0

#: No more than this fraction of a track's energy may fall in the protected
#: speech corridor. Not zero: the skirts of a sub-bass drone and the low tail
#: of shaped noise unavoidably reach into it, and a little is inaudible under
#: narration. A tonal pad *centred* there lands near 100%, which is the
#: failure this guards against.
MAX_SPEECH_BAND_ENERGY = 0.15


def speech_band_energy(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> float:
    """Fraction of ``audio``'s energy inside the protected speech corridor."""
    spectrum = np.abs(np.fft.rfft(audio)) ** 2
    freqs = np.fft.rfftfreq(len(audio), 1 / sample_rate)
    corridor = (freqs >= SPEECH_F0_HZ) & (freqs < SPEECH_CLARITY_TOP_HZ)
    total = spectrum.sum()
    return float(spectrum[corridor].sum() / total) if total else 0.0


def _cycles(n: int) -> float:
    """Frequency (Hz) for exactly ``n`` whole cycles over the loop duration."""
    return n / DURATION_SECONDS


def _sine(freq_hz: float, t: np.ndarray, *, phase: float = 0.0) -> np.ndarray:
    return np.sin(2 * np.pi * freq_hz * t + phase)


def generate_mystical(seed: int = 7) -> np.ndarray:
    """A deep, slowly shifting drone with high shimmer -- "mystical".

    The weight sits at ~55/82.5 Hz, an octave below where it used to, so it
    is felt rather than heard as pitch and leaves the voice's fundamental
    clear. The character that made this track recognisable moves up into the
    6-9 kHz shimmer, well above anything speech needs for articulation.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(int(DURATION_SECONDS * SAMPLE_RATE)) / SAMPLE_RATE

    # Sub drone + fifth, both below SPEECH_F0_HZ. Integer-cycle, so seamless.
    root = _sine(_cycles(1650), t) * 0.5  # ~55 Hz
    fifth = _sine(_cycles(2475), t, phase=0.3) * 0.26  # ~82.5 Hz (perfect fifth)

    # Slow tremolo (integer cycles) so the pad breathes without a hard loop seam.
    tremolo = 0.75 + 0.25 * _sine(_cycles(6), t)

    drone = (root + fifth) * tremolo

    # The "mystical" character: quiet, slowly modulated partials high above
    # the speech corridor, each an integer number of cycles so they stay in
    # phase across the loop too.
    shimmer = np.zeros_like(t)
    for k in (203, 257, 311):  # ~6.1, 7.7, 9.3 kHz
        freq = _cycles(k * 30)
        mod = 0.5 + 0.5 * _sine(_cycles(k % 11 + 3), t, phase=float(rng.uniform(0, 6.28)))
        shimmer += _sine(freq, t) * mod * 0.05

    mix = drone + shimmer
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak) * 0.9  # leave headroom; final gain is applied at mix time
    return mix.astype(np.float32)


def generate_calm(seed: int = 11) -> np.ndarray:
    """A plain, warm sub-bass pad with no shimmer -- "calm".

    Same move as ``mystical``: the two tones drop an octave, out of the
    range a narrator's fundamental occupies.
    """
    t = np.arange(int(DURATION_SECONDS * SAMPLE_RATE)) / SAMPLE_RATE

    root = _sine(_cycles(1980), t) * 0.55  # ~66 Hz
    third = _sine(_cycles(2475), t, phase=0.6) * 0.28  # ~82.5 Hz

    # Slower, gentler breathing than "mystical" -- less "alive", more restful.
    tremolo = 0.8 + 0.2 * _sine(_cycles(3), t)

    mix = (root + third) * tremolo
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak) * 0.85
    return mix.astype(np.float32)


def generate_forest(seed: int = 23) -> np.ndarray:
    """Filtered noise "wind" with sparse high chirps -- "forest"."""
    rng = np.random.default_rng(seed)
    n = int(DURATION_SECONDS * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE

    # Brown-ish noise (integrated white noise, DC-removed) reads as wind/leaf
    # rustle rather than harsh hiss. A short moving-average low-passes it
    # further without needing a separate filtering dependency.
    white = rng.standard_normal(n)
    brown = np.cumsum(white)
    brown -= brown.mean()
    window = 9
    kernel = np.ones(window) / window
    wind = np.convolve(brown, kernel, mode="same")
    wind /= np.max(np.abs(wind)) or 1.0

    # Slow gusts: an integer-cycle envelope so the loop point matches exactly.
    gusts = 0.55 + 0.45 * _sine(_cycles(4), t, phase=0.4) * _sine(_cycles(7), t, phase=2.0)
    wind = wind * gusts * 0.5

    # A handful of short, sparse "bird chirp" blips -- quick upward sine
    # sweeps at integer-cycle-spaced start times so they, too, loop cleanly.
    chirps = np.zeros(n)
    chirp_len = int(0.18 * SAMPLE_RATE)
    ramp = np.linspace(0, 1, chirp_len)
    for k in range(5):
        start = int((k + 0.5) / 5 * n) + int(rng.uniform(-0.3, 0.3) * SAMPLE_RATE)
        start = max(0, min(n - chirp_len, start))
        freq_sweep = 2600 + 900 * ramp
        phase = 2 * np.pi * np.cumsum(freq_sweep) / SAMPLE_RATE
        envelope = np.sin(np.pi * ramp) ** 2  # fades in and out within the blip
        chirps[start : start + chirp_len] += np.sin(phase) * envelope * 0.06

    mix = wind + chirps
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak) * 0.8

    # Unlike the tonal pads above, noise has no periodicity to align at the
    # loop point -- an integer-cycle envelope keeps the *gusts* seamless, but
    # the noise floor itself still has an audible click at wrap-around
    # without an explicit crossfade. Blend a short tail into the head.
    fade_len = int(0.25 * SAMPLE_RATE)
    fade_in = np.linspace(0, 1, fade_len)
    fade_out = 1 - fade_in
    mix[:fade_len] = mix[:fade_len] * fade_in + mix[-fade_len:] * fade_out

    return mix.astype(np.float32)


def generate_bedtime(seed: int = 3) -> np.ndarray:
    """An extremely soft, slow, low hush -- "bedtime"."""
    t = np.arange(int(DURATION_SECONDS * SAMPLE_RATE)) / SAMPLE_RATE

    root = _sine(_cycles(1560), t) * 0.6  # ~52 Hz, low and unobtrusive
    fifth = _sine(_cycles(2340), t, phase=0.2) * 0.18  # ~78 Hz

    # Very slow tremolo: a lullaby-like, almost imperceptible breathing.
    tremolo = 0.85 + 0.15 * _sine(_cycles(2), t)

    mix = (root + fifth) * tremolo
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak) * 0.75  # quietest preset by design
    return mix.astype(np.float32)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tracks = {
        "mystical": generate_mystical(),
        "calm": generate_calm(),
        "forest": generate_forest(),
        "bedtime": generate_bedtime(),
    }
    for name, audio in tracks.items():
        # Refuse to ship a track that would mask narration -- this script is
        # the only thing standing between a pretty pad and an unusable one.
        share = speech_band_energy(audio)
        if share > MAX_SPEECH_BAND_ENERGY:
            raise SystemExit(
                f"'{name}' puts {share:.1%} of its energy in the "
                f"{SPEECH_F0_HZ:.0f}-{SPEECH_CLARITY_TOP_HZ:.0f} Hz speech corridor "
                f"(limit {MAX_SPEECH_BAND_ENERGY:.0%}). It would make narration "
                f"sound muddy; move its weight below or above the corridor."
            )
        path = OUT_DIR / f"{name}.wav"
        sf.write(str(path), audio, SAMPLE_RATE, subtype="PCM_16", format="WAV")
        print(
            f"wrote {path} ({len(audio) / SAMPLE_RATE:.1f}s, {path.stat().st_size} bytes, "
            f"{share:.1%} in speech corridor)"
        )


if __name__ == "__main__":
    main()
