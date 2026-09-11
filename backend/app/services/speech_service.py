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
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from ai.audio_processing import write_wav
from ai.engine import (
    EngineError,
    SynthesisRequest,
    VoiceCloningEngine,
)
from ai.engine import (
    UnsupportedLanguageError as EngineUnsupportedLanguage,
)
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
from app.services.language import resolve as resolve_language
from app.services.storage import LocalStorage

logger = logging.getLogger(__name__)


@dataclass
class SpeechResult:
    generation: Generation
    notice: str | None


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

        try:
            resolved = resolve_language(
                self.engine,
                request.language,
                request.text,
                include_armenian=self.settings.enable_experimental_armenian,
            )
        except ValueError as exc:
            raise UnsupportedLanguageError(str(exc)) from exc

        generation_id = new_id("gen")
        try:
            result = self.engine.synthesize(
                SynthesisRequest(
                    profile=profile,
                    text=resolved.text,
                    language=resolved.engine_language,
                    exaggeration=request.exaggeration,
                    cfg_weight=request.cfg_weight,
                    temperature=request.temperature,
                    seed=request.seed,
                )
            )
        except EngineUnsupportedLanguage as exc:
            raise UnsupportedLanguageError(str(exc)) from exc
        except EngineError as exc:
            logger.exception("Synthesis failed for voice %s", voice.id)
            raise SynthesisFailedError(
                "Speech generation failed. Try shorter text or a different voice."
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected engine failure for voice %s", voice.id)
            raise EngineUnavailableError("The speech engine is currently unavailable.") from exc

        output_path = self.storage.generation_path(generation_id)
        write_wav(output_path, result.audio, result.sample_rate)
        size_bytes = output_path.stat().st_size

        generation = Generation(
            id=generation_id,
            voice_id=voice.id,
            text=request.text,
            language=resolved.requested,
            effective_text=resolved.text if resolved.experimental else None,
            filename=output_path.name,
            sample_rate=result.sample_rate,
            duration_seconds=round(result.duration_seconds, 3),
            size_bytes=size_bytes,
            generation_seconds=round(result.generation_seconds, 3),
            real_time_factor=round(result.real_time_factor, 4),
            engine=result.engine,
            watermarked=result.watermarked,
            experimental=resolved.experimental,
        )
        self.generations.add(generation)
        self.voices.mark_used(voice)
        self.audit.record(
            "speech.generated",
            subject_id=generation_id,
            actor=actor,
            detail={
                "voiceId": voice.id,
                "language": resolved.requested,
                "chars": len(request.text),
                "durationSeconds": generation.duration_seconds,
                "rtf": generation.real_time_factor,
                "experimental": resolved.experimental,
            },
        )
        return SpeechResult(generation=generation, notice=resolved.notice)

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
