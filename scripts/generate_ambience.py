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

Run manually to regenerate: ``python3 scripts/generate_ambience.py``
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24_000
DURATION_SECONDS = 30.0
OUT_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "assets" / "ambience"


def _cycles(n: int) -> float:
    """Frequency (Hz) for exactly ``n`` whole cycles over the loop duration."""
    return n / DURATION_SECONDS


def _sine(freq_hz: float, t: np.ndarray, *, phase: float = 0.0) -> np.ndarray:
    return np.sin(2 * np.pi * freq_hz * t + phase)


def generate_mystical(seed: int = 7) -> np.ndarray:
    """A soft, slowly shifting drone with faint high shimmer -- "mystical"."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(DURATION_SECONDS * SAMPLE_RATE)) / SAMPLE_RATE

    # Root drone + fifth + octave, all integer-cycle so the loop is seamless.
    # Frequencies land near a soft low pad (~110-165 Hz region).
    root = _sine(_cycles(3300), t) * 0.5  # ~110 Hz
    fifth = _sine(_cycles(4950), t, phase=0.3) * 0.28  # ~165 Hz (perfect fifth)
    octave = _sine(_cycles(6600), t, phase=1.1) * 0.14  # ~220 Hz

    # Slow tremolo (integer cycles) so the pad breathes without a hard loop seam.
    tremolo = 0.75 + 0.25 * _sine(_cycles(6), t)

    drone = (root + fifth + octave) * tremolo

    # Faint high "shimmer" -- a handful of quiet, slowly amplitude-modulated
    # high partials, each an integer number of cycles, so they stay in phase
    # across the loop too.
    shimmer = np.zeros_like(t)
    for k in (97, 131, 163):  # arbitrary high, inharmonic-ish integer counts
        freq = _cycles(k * 30)  # a few kHz range partials, still loop-exact
        mod = 0.5 + 0.5 * _sine(_cycles(k % 11 + 3), t, phase=float(rng.uniform(0, 6.28)))
        shimmer += _sine(freq, t) * mod * 0.015

    mix = drone + shimmer
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak) * 0.9  # leave headroom; final gain is applied at mix time
    return mix.astype(np.float32)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tracks = {
        "mystical": generate_mystical(),
    }
    for name, audio in tracks.items():
        path = OUT_DIR / f"{name}.wav"
        sf.write(str(path), audio, SAMPLE_RATE, subtype="PCM_16", format="WAV")
        print(f"wrote {path} ({len(audio) / SAMPLE_RATE:.1f}s, {path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
