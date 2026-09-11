"""Abstract voice cloning engine contract.

Every concrete engine (Chatterbox, F5-TTS, XTTS-v2, ...) implements this
interface.  The contract is deliberately narrow:

    create_voice(audio_path, ...)   -> VoiceProfile     (conditioning step)
    synthesize(profile, text, ...)  -> SynthesisResult  (generation step)

Some models can pre-compute and persist a speaker representation
("conditioning latents", "speaker embedding", "conditionals"); others need the
raw reference waveform at every call.  ``VoiceProfile`` covers both: it always
carries the path to the cleaned reference audio, and *optionally* a path to a
cached conditioning artefact.  Engines that cannot cache simply leave it None.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


class EngineError(RuntimeError):
    """Raised when the underlying model fails in a way the API should surface."""


class UnsupportedLanguageError(EngineError):
    """Raised when a language code is not supported by the loaded engine."""


@dataclass(frozen=True)
class EngineInfo:
    """Static description of a loaded engine, surfaced at ``GET /system/info``."""

    name: str
    variant: str
    device: str
    sample_rate: int
    languages: dict[str, str]
    supports_streaming: bool
    supports_cached_conditioning: bool
    watermarked: bool
    license: str
    notes: str = ""


@dataclass
class VoiceProfile:
    """Everything the engine needs to speak as one particular voice.

    Attributes
    ----------
    voice_id:
        Application-level identifier (``voice_ab12cd34``).
    reference_path:
        Cleaned, preprocessed reference WAV.  Always present -- it is the
        portable representation and lets us re-derive conditioning after a
        model upgrade.
    conditioning_path:
        Optional engine-specific cache (for Chatterbox: a ``conds.pt`` holding
        the speaker embedding, prompt speech tokens and S3Gen prompt features).
        Treated as a disposable derived artefact.
    engine:
        Name of the engine that produced ``conditioning_path``.  A mismatch
        invalidates the cache.
    metadata:
        Free-form engine notes persisted alongside the voice.
    """

    voice_id: str
    reference_path: Path
    conditioning_path: Path | None = None
    engine: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SynthesisRequest:
    """One text-to-speech call."""

    profile: VoiceProfile
    text: str
    language: str = "en"
    exaggeration: float | None = None
    cfg_weight: float | None = None
    temperature: float | None = None
    seed: int | None = None


@dataclass
class SynthesisResult:
    """Mono float32 audio in ``[-1, 1]`` plus timing telemetry."""

    audio: np.ndarray
    sample_rate: int
    duration_seconds: float
    generation_seconds: float
    watermarked: bool
    engine: str
    language: str

    @property
    def real_time_factor(self) -> float:
        """RTF = generation wall time / duration of generated audio.

        Lower is better; < 1.0 means faster than real time.
        """
        if self.duration_seconds <= 0:
            return float("inf")
        return self.generation_seconds / self.duration_seconds


class VoiceCloningEngine(abc.ABC):
    """Interface implemented by every backend model."""

    name: str = "abstract"

    # -- lifecycle ---------------------------------------------------------
    @abc.abstractmethod
    def load(self) -> None:
        """Load weights into memory. Must be idempotent and thread-safe."""

    @abc.abstractmethod
    def unload(self) -> None:
        """Release weights and GPU memory."""

    @property
    @abc.abstractmethod
    def is_loaded(self) -> bool: ...

    @abc.abstractmethod
    def info(self) -> EngineInfo:
        """Describe the engine. Must work *without* loading weights."""

    # -- voice profiles ----------------------------------------------------
    @abc.abstractmethod
    def create_voice(
        self,
        voice_id: str,
        audio_path: str | Path,
        *,
        workdir: str | Path,
    ) -> VoiceProfile:
        """Derive a reusable voice profile from a preprocessed reference clip.

        ``audio_path`` is guaranteed to be a mono WAV at the engine's native
        sample rate (see :meth:`info`), already trimmed and normalised by
        :mod:`ai.audio_processing`.
        """

    # -- synthesis ---------------------------------------------------------
    @abc.abstractmethod
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Generate speech for ``request.text`` in ``request.profile``'s voice."""

    # -- helpers -----------------------------------------------------------
    def supports_language(self, language: str) -> bool:
        return language.lower() in self.info().languages

    def validate_language(self, language: str) -> str:
        lang = language.lower()
        if not self.supports_language(lang):
            supported = ", ".join(sorted(self.info().languages))
            raise UnsupportedLanguageError(
                f"Language '{language}' is not supported by engine "
                f"'{self.name}'. Supported: {supported}"
            )
        return lang
