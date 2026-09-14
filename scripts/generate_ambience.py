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


def generate_calm(seed: int = 11) -> np.ndarray:
    """A plain, warm two-tone pad with no shimmer -- "calm"."""
    t = np.arange(int(DURATION_SECONDS * SAMPLE_RATE)) / SAMPLE_RATE

    root = _sine(_cycles(3960), t) * 0.55  # ~132 Hz
    third = _sine(_cycles(4950), t, phase=0.6) * 0.3  # ~165 Hz (major third-ish)

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
    wind /= (np.max(np.abs(wind)) or 1.0)

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

    root = _sine(_cycles(2310), t) * 0.6  # ~77 Hz, low and unobtrusive
    fifth = _sine(_cycles(3465), t, phase=0.2) * 0.18  # ~115.5 Hz

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
        path = OUT_DIR / f"{name}.wav"
        sf.write(str(path), audio, SAMPLE_RATE, subtype="PCM_16", format="WAV")
        print(f"wrote {path} ({len(audio) / SAMPLE_RATE:.1f}s, {path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
