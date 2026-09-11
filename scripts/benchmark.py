#!/usr/bin/env python3
"""Measure the numbers that decide the deployment shape.

    python scripts/benchmark.py --engine chatterbox --variant multilingual
    python scripts/benchmark.py --engine mock            # plumbing check, no weights

Reports model load time, voice conditioning time, and per-generation latency
and Real-Time Factor:

    RTF = generation wall time / duration of the generated audio

RTF < 1.0 means faster than real time. RTF is the number that decides whether
``POST /speech`` can stay synchronous: at RTF 0.3, 30 seconds of speech takes
~9 s and fits comfortably in an HTTP request; at RTF 3.0 it takes 90 s and the
job-queue design in docs/ARCHITECTURE.md becomes necessary.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.audio_processing import write_wav
from ai.engine import SynthesisRequest
from ai.model_loader import describe_device
from ai.registry import get_engine

SENTENCES = [
    "Hello. This is my cloned voice.",
    "The quick brown fox jumps over the lazy dog.",
    (
        "Voice cloning systems are evaluated on speaker similarity and naturalness, "
        "and the trade-off between them depends heavily on the reference recording."
    ),
]


def synthetic_reference(path: Path, seconds: float = 12.0, sample_rate: int = 24_000) -> Path:
    t = np.arange(int(seconds * sample_rate), dtype=np.float32) / sample_rate
    signal = sum(
        gain * np.sin(2 * np.pi * 130 * harmonic * t)
        for harmonic, gain in ((1, 1.0), (2, 0.5), (3, 0.25), (4, 0.12))
    )
    signal *= 0.6 + 0.4 * np.sin(2 * np.pi * 3.2 * t)
    return write_wav(path, (0.5 * signal / np.max(np.abs(signal))).astype(np.float32), sample_rate)


def peak_vram_mb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.max_memory_allocated() / 1024**2
    except ImportError:
        pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--engine", default="chatterbox", choices=["chatterbox", "mock"])
    parser.add_argument("--variant", default="multilingual")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--language", default="en")
    parser.add_argument("--runs", type=int, default=3, help="Repeats per sentence.")
    parser.add_argument("--reference", type=Path, help="Reference WAV (synthesised if omitted).")
    parser.add_argument("--json", type=Path, help="Write the full report here.")
    args = parser.parse_args()

    workdir = Path(".benchmark")
    workdir.mkdir(exist_ok=True)
    reference = args.reference or synthetic_reference(workdir / "reference.wav")

    kwargs = {"variant": args.variant, "device": args.device} if args.engine == "chatterbox" else {}
    engine = get_engine(args.engine, **kwargs)

    print(f"engine={args.engine} variant={args.variant} device={engine.info().device}")
    print("Loading model ...")
    started = time.perf_counter()
    engine.load()
    load_seconds = time.perf_counter() - started
    print(f"  model load:        {load_seconds:8.2f} s")

    started = time.perf_counter()
    profile = engine.create_voice("voice_benchmark01", reference, workdir=workdir / "voice")
    conditioning_seconds = time.perf_counter() - started
    print(f"  voice conditioning:{conditioning_seconds:8.2f} s")

    print(f"\n{'chars':>6} {'audio s':>9} {'gen s':>9} {'RTF':>7}")
    print("-" * 35)
    rows = []
    for sentence in SENTENCES:
        for _ in range(args.runs):
            result = engine.synthesize(
                SynthesisRequest(profile=profile, text=sentence, language=args.language)
            )
            rows.append(
                {
                    "chars": len(sentence),
                    "audio_seconds": round(result.duration_seconds, 3),
                    "generation_seconds": round(result.generation_seconds, 3),
                    "rtf": round(result.real_time_factor, 4),
                }
            )
            print(
                f"{len(sentence):>6} {result.duration_seconds:9.2f} "
                f"{result.generation_seconds:9.2f} {result.real_time_factor:7.3f}"
            )

    rtfs = [row["rtf"] for row in rows]
    report = {
        "engine": args.engine,
        "variant": args.variant,
        "device": describe_device(engine.info().device),
        "model_load_seconds": round(load_seconds, 3),
        "voice_conditioning_seconds": round(conditioning_seconds, 3),
        "peak_vram_mb": peak_vram_mb(),
        "rtf": {
            "mean": round(statistics.fmean(rtfs), 4),
            "median": round(statistics.median(rtfs), 4),
            "min": round(min(rtfs), 4),
            "max": round(max(rtfs), 4),
        },
        "runs": rows,
    }

    print("\n--- summary ---")
    print(f"  RTF mean/median:   {report['rtf']['mean']:.3f} / {report['rtf']['median']:.3f}")
    if report["peak_vram_mb"]:
        print(f"  peak VRAM:         {report['peak_vram_mb']:.0f} MB")
    if report["rtf"]["mean"] < 1.0:
        print("  -> faster than real time; synchronous POST /speech is appropriate.")
    else:
        print("  -> slower than real time; consider the job-queue design for long text.")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
