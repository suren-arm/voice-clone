"""Bootstraps the system-owned "default voice" rows.

Default voices are real :class:`~app.models.voice.Voice` rows like any
cloned voice -- ``source="system"``, ``engine="espeak-ng"`` -- so every
existing code path (listing, sampling, generation, the frontend's voice
picker) works for them unchanged. :func:`ensure_default_voices` creates them
once, idempotently, at process startup; :mod:`app.services.speech_service`
branches on ``voice.engine`` to route generation to espeak-ng instead of the
cloning engine.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from ai.audio_processing import write_wav
from ai.espeak_engine import DEFAULT_VOICES, EspeakError, espeak_available, synthesize_espeak
from app.core.security import new_id
from app.db.base import utcnow
from app.models.voice import Voice
from app.services.storage import LocalStorage

logger = logging.getLogger(__name__)

_SAMPLE_TEXT = {
    "en": "Hello. This is a default voice you can use without recording yourself.",
    "hy": "Բարև ձեզ։ Սա կանխադրված ձայն է, որը կարող եք օգտագործել առանց ձայնագրելու։",
}

DEFAULT_VOICE_ENGINE = "espeak-ng"


def ensure_default_voices(session, storage: LocalStorage) -> None:
    """Create any missing default-voice rows. Safe to call on every startup."""
    if not espeak_available():
        logger.warning("espeak-ng not found on PATH; default voices will not be available")
        return

    existing_variants = set(
        session.scalars(select(Voice.engine_variant).where(Voice.engine == DEFAULT_VOICE_ENGINE))
    )

    created = 0
    for spec in DEFAULT_VOICES:
        if spec.espeak_voice in existing_variants:
            continue
        try:
            audio, sr = synthesize_espeak(
                _SAMPLE_TEXT.get(spec.language, _SAMPLE_TEXT["en"]), spec.espeak_voice
            )
        except EspeakError:
            logger.exception("Could not synthesize sample audio for default voice %s", spec.id)
            continue

        voice_id = new_id("voice")
        reference_path = storage.reference_path(voice_id)
        write_wav(reference_path, audio, sr)
        duration = len(audio) / sr

        session.add(
            Voice(
                id=voice_id,
                name=spec.name,
                language=spec.language,
                engine=DEFAULT_VOICE_ENGINE,
                engine_variant=spec.espeak_voice,
                has_conditioning_cache=False,
                reference_filename=reference_path.name,
                reference_duration_seconds=round(duration, 3),
                reference_sample_rate=sr,
                source_container="wav",
                source="system",
                consent_given=True,
                consent_at=utcnow(),
                consent_statement=(
                    "System-provided default voice (espeak-ng); not a recording of any person."
                ),
            )
        )
        created += 1

    if created:
        session.commit()
        logger.info("Created %d default voice(s)", created)
