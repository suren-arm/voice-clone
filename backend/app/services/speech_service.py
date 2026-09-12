"""Text-to-speech generation.

Synchronous by design for the MVP. Chatterbox on a modern GPU generates at an
RTF well under 1.0, so a typical 2000-character request finishes in seconds --
inside any sane HTTP timeout, and far simpler than a queue. The exact threshold
at which this must become ``POST /jobs`` + ``GET /jobs/{id}`` is written down in
docs/ARCHITECTURE.md; the response shape below (a ``Generation`` resource with
an ``audioUrl``) is already the shape a job-completion payload would have, so
that migration does not change the client contract.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from ai.audio_mix import AudioMixError, ffmpeg_available, mix_with_background
from ai.audio_processing import write_wav
from ai.engine import (
    EngineError,
    SynthesisRequest,
    VoiceCloningEngine,
)
from ai.engine import (
    UnsupportedLanguageError as EngineUnsupportedLanguage,
)
from ai.espeak_engine import ESPEAK_SAMPLE_RATE, EspeakError, synthesize_espeak
from ai.text_chunking import chunk_text
from app.core.config import Settings
from app.core.errors import (
    EngineUnavailableError,
    GenerationNotFoundError,
    SynthesisFailedError,
    UnsupportedLanguageError,
    ValidationError,
)
from app.core.security import is_safe_id, new_id
from app.models.generation import Generation
from app.models.voice import Voice
from app.repositories.audit_repo import AuditRepository
from app.repositories.generation_repo import GenerationRepository
from app.repositories.voice_repo import VoiceRepository
from app.schemas.speech import SpeechRequest
from app.services.default_voices import DEFAULT_VOICE_ENGINE
from app.services.language import resolve as resolve_language
from app.services.storage import LocalStorage

logger = logging.getLogger(__name__)

#: Chunk boundary for long-form narration (fairy tales especially): each
#: piece is synthesized separately and concatenated, so one failure doesn't
#: lose the whole story and very long input doesn't degrade a single call.
_CHUNK_MAX_CHARS = 900
_CHUNK_GAP_SECONDS = 0.35


@dataclass
class SpeechResult:
    generation: Generation
    notice: str | None
    background_applied: bool = False
    background_notice: str | None = None


@dataclass
class SpeechService:
    session: Session
    settings: Settings
    engine: VoiceCloningEngine
    storage: LocalStorage

    def __post_init__(self) -> None:
        self.generations = GenerationRepository(self.session)
        self.voices = VoiceRepository(self.session)
        self.audit = AuditRepository(self.session)

    # -- generate ----------------------------------------------------------
    def generate(
        self,
        request: SpeechRequest,
        voice: Voice,
        *,
        profile,
        actor: str | None = None,
    ) -> SpeechResult:
        if len(request.text) > self.settings.max_text_chars:
            raise ValidationError(
                f"Text is {len(request.text)} characters; the limit is "
                f"{self.settings.max_text_chars}.",
                details={"maxChars": self.settings.max_text_chars},
            )

        if voice.engine == DEFAULT_VOICE_ENGINE:
            resolved_language, effective_text, experimental, notice, synth = (
                voice.language,
                None,
                False,
                None,
                self._synthesize_default_voice(voice, request.text),
            )
        else:
            try:
                resolved = resolve_language(
                    self.engine,
                    request.language,
                    request.text,
                    include_armenian=self.settings.enable_experimental_armenian,
                )
            except ValueError as exc:
                raise UnsupportedLanguageError(str(exc)) from exc
            resolved_language = resolved.requested
            effective_text = resolved.text if resolved.experimental else None
            experimental = resolved.experimental
            notice = resolved.notice
            synth = self._synthesize_cloned_voice(resolved.text, resolved.engine_language, request, profile)

        audio_out, sample_rate, generation_seconds, watermarked, engine_name = synth

        generation_id = new_id("gen")
        output_path = self.storage.generation_path(generation_id)
        write_wav(output_path, audio_out, sample_rate)

        background_applied = False
        background_notice: str | None = None
        if request.background_sound != "none":
            if ffmpeg_available():
                try:
                    mix_with_background(
                        output_path,
                        request.background_sound,
                        volume_percent=request.background_volume,
                        out_path=output_path,
                    )
                    background_applied = True
                except AudioMixError:
                    logger.exception("Background mixing failed for generation %s", generation_id)
                    background_notice = (
                        "Background sound could not be applied; the narration was generated "
                        "without it."
                    )
            else:
                background_notice = (
                    "Background sound is unavailable on this server (ffmpeg is not installed); "
                    "the narration was generated without it."
                )

        size_bytes = output_path.stat().st_size
        duration_seconds = len(audio_out) / sample_rate if sample_rate else 0.0
        real_time_factor = generation_seconds / duration_seconds if duration_seconds > 0 else 0.0

        generation = Generation(
            id=generation_id,
            voice_id=voice.id,
            text=request.text,
            language=resolved_language,
            effective_text=effective_text,
            filename=output_path.name,
            sample_rate=sample_rate,
            duration_seconds=round(duration_seconds, 3),
            size_bytes=size_bytes,
            generation_seconds=round(generation_seconds, 3),
            real_time_factor=round(real_time_factor, 4),
            engine=engine_name,
            watermarked=watermarked,
            experimental=experimental,
        )
        self.generations.add(generation)
        self.voices.mark_used(voice)
        self.audit.record(
            "speech.generated",
            subject_id=generation_id,
            actor=actor,
            detail={
                "voiceId": voice.id,
                "language": resolved_language,
                "chars": len(request.text),
                "durationSeconds": generation.duration_seconds,
                "rtf": generation.real_time_factor,
                "experimental": experimental,
                "backgroundSound": request.background_sound,
                "backgroundApplied": background_applied,
            },
        )
        return SpeechResult(
            generation=generation,
            notice=notice,
            background_applied=background_applied,
            background_notice=background_notice,
        )

    # -- synthesis backends --------------------------------------------------
    def _synthesize_cloned_voice(
        self, text: str, engine_language: str, request: SpeechRequest, profile
    ) -> tuple[np.ndarray, int, float, bool, str]:
        """Chunk-safe synthesis via the injected cloning engine (Chatterbox)."""
        chunks = chunk_text(text, max_chars=_CHUNK_MAX_CHARS)
        pieces: list[np.ndarray] = []
        sample_rate = self.engine.info().sample_rate
        watermarked = False
        engine_name = self.engine.name
        total_generation_seconds = 0.0
        try:
            for index, chunk in enumerate(chunks):
                result = self.engine.synthesize(
                    SynthesisRequest(
                        profile=profile,
                        text=chunk,
                        language=engine_language,
                        exaggeration=request.exaggeration,
                        cfg_weight=request.cfg_weight,
                        temperature=request.temperature,
                        seed=request.seed,
                    )
                )
                sample_rate = result.sample_rate
                watermarked = result.watermarked
                engine_name = result.engine
                total_generation_seconds += result.generation_seconds
                if index > 0:
                    pieces.append(np.zeros(int(_CHUNK_GAP_SECONDS * sample_rate), dtype=np.float32))
                pieces.append(result.audio)
        except EngineUnsupportedLanguage as exc:
            raise UnsupportedLanguageError(str(exc)) from exc
        except EngineError as exc:
            logger.exception("Synthesis failed")
            raise SynthesisFailedError(
                "Speech generation failed. Try shorter text or a different voice."
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected engine failure")
            raise EngineUnavailableError("The speech engine is currently unavailable.") from exc

        audio_out = np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)
        return audio_out, sample_rate, total_generation_seconds, watermarked, engine_name

    def _synthesize_default_voice(
        self, voice: Voice, text: str
    ) -> tuple[np.ndarray, int, float, bool, str]:
        """Chunk-safe synthesis via espeak-ng for a system default voice."""
        espeak_voice = voice.engine_variant or "en-us"
        chunks = chunk_text(text.strip(), max_chars=_CHUNK_MAX_CHARS)
        pieces: list[np.ndarray] = []
        sample_rate = ESPEAK_SAMPLE_RATE
        started = time.perf_counter()
        try:
            for index, chunk in enumerate(chunks):
                audio, sample_rate = synthesize_espeak(chunk, espeak_voice)
                if index > 0:
                    pieces.append(np.zeros(int(_CHUNK_GAP_SECONDS * sample_rate), dtype=np.float32))
                pieces.append(audio)
        except EspeakError as exc:
            logger.exception("espeak-ng synthesis failed for voice %s", voice.id)
            raise EngineUnavailableError(
                "The default voice engine is currently unavailable."
            ) from exc

        audio_out = np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)
        generation_seconds = time.perf_counter() - started
        return audio_out, sample_rate, generation_seconds, False, DEFAULT_VOICE_ENGINE

    # -- read --------------------------------------------------------------
    def get(self, generation_id: str) -> Generation:
        if not is_safe_id(generation_id, "gen"):
            raise GenerationNotFoundError(f"Generation '{generation_id}' was not found.")
        generation = self.generations.get(generation_id)
        if generation is None:
            raise GenerationNotFoundError(f"Generation '{generation_id}' was not found.")
        return generation

    def list(
        self, *, voice_id: str | None, limit: int, offset: int
    ) -> tuple[list[Generation], int]:
        return (
            self.generations.list(voice_id=voice_id, limit=limit, offset=offset),
            self.generations.count(voice_id=voice_id),
        )

    def audio_file(self, generation_id: str) -> tuple[Generation, Path]:
        generation = self.get(generation_id)
        path = self.storage.generation_path(generation.id)
        if not path.is_file():
            raise GenerationNotFoundError("The audio for this generation is no longer available.")
        return generation, path

    # -- delete ------------------------------------------------------------
    def delete(self, generation_id: str, *, actor: str | None = None) -> str:
        generation = self.get(generation_id)
        self.generations.delete(generation)
        self.storage.delete_generation(generation.id)
        self.audit.record("speech.deleted", subject_id=generation.id, actor=actor)
        return generation.id
