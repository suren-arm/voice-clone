"""Deterministic engine used by CI, unit tests and CPU-only dev machines.

It implements the full :class:`VoiceCloningEngine` contract -- including the
conditioning-cache round trip -- without torch or any model weights, so the
API, storage and frontend can be exercised end to end in seconds.

The "voice" is a formant-ish additive tone whose pitch is derived from a hash
of the reference audio, and the "speech" is that tone amplitude-modulated by a
syllable envelope derived from the text. It sounds nothing like speech; it is
exactly as long as real speech would be, which is what the tests care about.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from ai.engine import (
    EngineError,
    EngineInfo,
    SynthesisRequest,
    SynthesisResult,
    VoiceCloningEngine,
    VoiceProfile,
)

MOCK_SAMPLE_RATE = 24_000
CONDITIONING_FILENAME = "conds.json"

#: Same language set as Chatterbox multilingual, so tests exercise real codes.
MOCK_LANGUAGES: dict[str, str] = {
    "ar": "Arabic",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sv": "Swedish",
    "sw": "Swahili",
    "tr": "Turkish",
    "zh": "Chinese",
}

#: Roughly average speaking rate, used to make generated durations plausible.
_CHARS_PER_SECOND = 14.0


class MockEngine(VoiceCloningEngine):
    """A fast, dependency-free stand-in for a real cloning model."""

    name = "mock"

    def __init__(self, *, latency_seconds: float = 0.0) -> None:
        self._loaded = False
        self._latency = latency_seconds

    # -- lifecycle ---------------------------------------------------------
    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def info(self) -> EngineInfo:
        return EngineInfo(
            name=self.name,
            variant="sine",
            device="cpu",
            sample_rate=MOCK_SAMPLE_RATE,
            languages=dict(MOCK_LANGUAGES),
            supports_streaming=False,
            supports_cached_conditioning=True,
            watermarked=False,
            license="MIT",
            notes="Test double. Produces tones, not speech. Never enable in production.",
        )

    # -- voice profiles ----------------------------------------------------
    def create_voice(
        self, voice_id: str, audio_path: str | Path, *, workdir: str | Path
    ) -> VoiceProfile:
        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise EngineError(f"Reference audio not found: {audio_path}")
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        self.load()

        digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        base_hz = 90.0 + (int(digest[:8], 16) % 160)  # 90-250 Hz
        conditioning_path = workdir / CONDITIONING_FILENAME
        conditioning_path.write_text(
            json.dumps({"voice_id": voice_id, "base_hz": base_hz, "digest": digest[:16]}),
            encoding="utf-8",
        )
        return VoiceProfile(
            voice_id=voice_id,
            reference_path=audio_path,
            conditioning_path=conditioning_path,
            engine=self.name,
            metadata={"base_hz": base_hz},
        )

    # -- synthesis ---------------------------------------------------------
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        text = request.text.strip()
        if not text:
            raise EngineError("Cannot synthesize empty text.")
        language = self.validate_language(request.language)
        self.load()

        base_hz = self._base_hz(request.profile)
        started = time.perf_counter()
        if self._latency:
            time.sleep(self._latency)

        duration = max(0.6, len(text) / _CHARS_PER_SECOND)
        t = np.arange(int(duration * MOCK_SAMPLE_RATE), dtype=np.float32) / MOCK_SAMPLE_RATE

        wave = np.zeros_like(t)
        for harmonic, gain in ((1, 1.0), (2, 0.45), (3, 0.2)):
            wave += gain * np.sin(2 * np.pi * base_hz * harmonic * t)
        syllable_hz = 4.0
        envelope = 0.55 + 0.45 * np.sin(2 * np.pi * syllable_hz * t - np.pi / 2)
        audio = (wave * envelope).astype(np.float32)
        peak = float(np.max(np.abs(audio))) or 1.0
        audio = (audio / peak * 0.7).astype(np.float32)

        generation_seconds = time.perf_counter() - started
        return SynthesisResult(
            audio=audio,
            sample_rate=MOCK_SAMPLE_RATE,
            duration_seconds=duration,
            generation_seconds=generation_seconds,
            watermarked=False,
            engine=self.name,
            language=language,
        )

    def _base_hz(self, profile: VoiceProfile) -> float:
        cache = profile.conditioning_path
        if cache and Path(cache).is_file():
            try:
                return float(json.loads(Path(cache).read_text(encoding="utf-8"))["base_hz"])
            except (ValueError, KeyError, OSError):
                pass
        reference = Path(profile.reference_path)
        if not reference.is_file():
            raise EngineError(
                f"Reference audio for voice {profile.voice_id} is missing; "
                "the voice must be recreated."
            )
        digest = hashlib.sha256(reference.read_bytes()).hexdigest()
        return 90.0 + (int(digest[:8], 16) % 160)
