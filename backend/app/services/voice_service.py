"""Voice profile lifecycle: validate -> preprocess -> condition -> persist."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from ai.audio_processing import (
    AudioValidationError as EngineAudioError,
)
from ai.audio_processing import (
    preprocess_reference,
)
from ai.engine import EngineError, VoiceCloningEngine, VoiceProfile
from app.core.config import Settings
from app.core.errors import (
    AudioValidationError,
    ConsentRequiredError,
    EngineUnavailableError,
    PayloadTooLargeError,
    QuotaExceededError,
    ValidationError,
    VoiceNotFoundError,
)
from app.core.security import is_safe_id, new_id, sanitize_display_name, sanitize_filename
from app.db.base import utcnow
from app.models.voice import Voice
from app.repositories.audit_repo import AuditRepository
from app.repositories.generation_repo import GenerationRepository
from app.repositories.voice_repo import VoiceRepository
from app.schemas.voice import CONSENT_STATEMENT, VoiceCreateForm
from app.services.language import is_supported
from app.services.storage import LocalStorage

logger = logging.getLogger(__name__)


@dataclass
class VoiceService:
    session: Session
    settings: Settings
    engine: VoiceCloningEngine
    storage: LocalStorage

    def __post_init__(self) -> None:
        self.voices = VoiceRepository(self.session)
        self.generations = GenerationRepository(self.session)
        self.audit = AuditRepository(self.session)

    # -- create ------------------------------------------------------------
    def create(
        self,
        form: VoiceCreateForm,
        *,
        audio_bytes: bytes,
        filename: str | None,
        actor: str | None = None,
    ) -> Voice:
        if self.settings.require_consent and not form.consent:
            raise ConsentRequiredError(
                "You must confirm that this is your voice, or that you have the "
                "speaker's permission, before a voice profile can be created.",
                details={"statement": CONSENT_STATEMENT},
            )

        if len(audio_bytes) > self.settings.max_upload_bytes:
            raise PayloadTooLargeError(
                f"Audio file is {len(audio_bytes) / 1024 / 1024:.1f} MB; the limit is "
                f"{self.settings.max_upload_bytes / 1024 / 1024:.0f} MB.",
                details={"maxBytes": self.settings.max_upload_bytes},
            )
        if not audio_bytes:
            raise AudioValidationError("No audio was uploaded.")

        if not is_supported(
            self.engine, form.language, include_armenian=self.settings.enable_experimental_armenian
        ):
            raise ValidationError(f"Language '{form.language}' is not supported.")

        if self.voices.count() >= self.settings.max_voices:
            raise QuotaExceededError(
                f"The voice limit of {self.settings.max_voices} has been reached. "
                "Delete a voice before creating another.",
            )

        voice_id = new_id("voice")
        safe_source_name = sanitize_filename(filename)
        voice_dir = self.storage.voice_dir(voice_id, create=True)
        reference_path = self.storage.reference_path(voice_id)

        try:
            info = preprocess_reference(
                audio_bytes,
                reference_path,
                filename=safe_source_name,
                sample_rate=self.engine.info().sample_rate,
                min_seconds=self.settings.min_reference_seconds,
                max_seconds=self.settings.max_reference_seconds,
            )
        except EngineAudioError as exc:
            self.storage.delete_voice(voice_id)
            raise AudioValidationError(str(exc)) from exc

        try:
            profile = self.engine.create_voice(voice_id, info.path, workdir=voice_dir)
        except EngineError as exc:
            self.storage.delete_voice(voice_id)
            logger.exception("Voice conditioning failed for %s", voice_id)
            raise EngineUnavailableError(
                "The voice model could not process this recording. Please try again."
            ) from exc

        voice = Voice(
            id=voice_id,
            name=sanitize_display_name(form.name),
            language=form.language,
            engine=self.engine.name,
            engine_variant=self.engine.info().variant,
            has_conditioning_cache=profile.conditioning_path is not None,
            reference_filename=info.path.name,
            reference_duration_seconds=info.duration_seconds,
            reference_sample_rate=info.sample_rate,
            source_container=info.container,
            source=form.source,
            consent_given=True,
            consent_at=utcnow(),
            consent_statement=CONSENT_STATEMENT,
        )
        self.voices.add(voice)

        self.storage.write_voice_metadata(
            voice_id,
            {
                "id": voice_id,
                "name": voice.name,
                "language": voice.language,
                "createdAt": voice.created_at.isoformat() if voice.created_at else None,
                "engine": voice.engine,
                "engineVariant": voice.engine_variant,
                "reference": {
                    "filename": info.path.name,
                    "durationSeconds": info.duration_seconds,
                    "sampleRate": info.sample_rate,
                    "sourceContainer": info.container,
                    "peakDbfs": info.peak_dbfs,
                    "trimmedSeconds": info.trimmed_seconds,
                    "originalFilename": safe_source_name,
                },
                "consent": {"given": True, "statement": CONSENT_STATEMENT},
                "engineMetadata": profile.metadata,
            },
        )
        self.audit.record(
            "voice.created",
            subject_id=voice_id,
            actor=actor,
            detail={
                "language": voice.language,
                "source": voice.source,
                "durationSeconds": info.duration_seconds,
                "consent": True,
            },
        )
        logger.info(
            "Created voice %s (%.1fs reference, %s)",
            voice_id,
            info.duration_seconds,
            voice.language,
        )
        return voice

    # -- read --------------------------------------------------------------
    def get(self, voice_id: str) -> Voice:
        if not is_safe_id(voice_id, "voice"):
            raise VoiceNotFoundError(f"Voice '{voice_id}' was not found.")
        voice = self.voices.get(voice_id)
        if voice is None:
            raise VoiceNotFoundError(f"Voice '{voice_id}' was not found.")
        return voice

    def list(self, *, limit: int, offset: int) -> tuple[list[Voice], int]:
        return self.voices.list(limit=limit, offset=offset), self.voices.count()

    def reference_file(self, voice_id: str) -> Path:
        voice = self.get(voice_id)
        path = self.storage.reference_path(voice.id)
        if not path.is_file():
            raise VoiceNotFoundError("The reference audio for this voice is no longer available.")
        return path

    def profile_for(self, voice: Voice) -> VoiceProfile:
        """Rebuild the engine-facing profile from persisted state."""
        voice_dir = self.storage.voice_dir(voice.id)
        conditioning = None
        if voice.has_conditioning_cache:
            candidates = list(voice_dir.glob("conds.*"))
            conditioning = candidates[0] if candidates else None
        return VoiceProfile(
            voice_id=voice.id,
            reference_path=self.storage.reference_path(voice.id),
            conditioning_path=conditioning,
            engine=voice.engine,
        )

    # -- delete ------------------------------------------------------------
    def delete(self, voice_id: str, *, actor: str | None = None) -> str:
        """Delete the voice, its reference audio, its conditioning cache and
        every generation made with it.

        This is the user's "undo" for consent, so it has to be complete: no
        orphaned audio, no reusable speaker representation left behind.
        """
        voice = self.get(voice_id)
        filenames = self.generations.filenames_for_voice(voice.id)
        generation_count = len(filenames)

        self.voices.delete(voice)  # cascades to generation rows
        for filename in filenames:
            self.storage.delete_generation_file(filename)
        self.storage.delete_voice(voice.id)

        self.audit.record(
            "voice.deleted",
            subject_id=voice.id,
            actor=actor,
            detail={"generationsRemoved": generation_count},
        )
        logger.info("Deleted voice %s and %d generations", voice.id, generation_count)
        return voice.id
