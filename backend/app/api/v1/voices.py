"""``/api/v1/voices`` -- voice profile CRUD."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import (
    PaginationDep,
    SettingsDep,
    VoiceServiceDep,
    limit_voice_creation,
)
from app.core.errors import PayloadTooLargeError
from app.core.rate_limit import client_key
from app.models.voice import Voice
from app.schemas.common import DeletedResponse, ErrorResponse, Page, PageMeta
from app.schemas.voice import VoiceCreateForm, VoiceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voices", tags=["voices"])

_ERRORS = {
    400: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


def _to_response(voice: Voice, prefix: str) -> VoiceResponse:
    return VoiceResponse(
        id=voice.id,
        name=voice.name,
        language=voice.language,
        created_at=voice.created_at,
        engine=voice.engine,
        engine_variant=voice.engine_variant,
        reference_duration_seconds=voice.reference_duration_seconds,
        reference_sample_rate=voice.reference_sample_rate,
        source=voice.source,
        generation_count=voice.generation_count,
        last_used_at=voice.last_used_at,
        consent_given=voice.consent_given,
        has_conditioning_cache=voice.has_conditioning_cache,
        sample_url=f"{prefix}/voices/{voice.id}/sample",
    )


async def _read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    """Stream the upload to memory, aborting as soon as the limit is passed.

    Reading in chunks matters: ``await upload.read()`` on a 2 GB body would
    happily buffer all of it before any size check could run.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                f"Audio file exceeds the {max_bytes / 1024 / 1024:.0f} MB limit.",
                details={"maxBytes": max_bytes},
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "",
    response_model=VoiceResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Create a voice profile from a reference recording",
    dependencies=[Depends(limit_voice_creation)],
)
async def create_voice(
    request: Request,
    service: VoiceServiceDep,
    settings: SettingsDep,
    name: str = Form(..., max_length=200, description="Display name for the voice."),
    language: str = Form("en", max_length=8, description="Primary language code."),
    consent: bool = Form(
        False,
        description="Must be true. Confirms the speaker is you or has given permission.",
    ),
    source: str = Form("record", pattern="^(upload|record)$"),
    audio: UploadFile = File(..., description="Reference clip: 10-30s of natural speech."),
) -> VoiceResponse:
    audio_bytes = await _read_upload(audio, settings.max_upload_bytes)
    form = VoiceCreateForm(name=name, language=language, consent=consent, source=source)

    # Conditioning runs the speaker encoder and speech tokenizer: seconds of
    # blocking compute. Off the event loop it goes.
    voice = await run_in_threadpool(
        service.create,
        form,
        audio_bytes=audio_bytes,
        filename=audio.filename,
        actor=client_key(request),
    )
    return _to_response(voice, settings.api_v1_prefix)


@router.get("", response_model=Page[VoiceResponse], summary="List voice profiles")
def list_voices(
    service: VoiceServiceDep, settings: SettingsDep, pagination: PaginationDep
) -> Page[VoiceResponse]:
    voices, total = service.list(limit=pagination.limit, offset=pagination.offset)
    return Page[VoiceResponse](
        items=[_to_response(voice, settings.api_v1_prefix) for voice in voices],
        meta=PageMeta(total=total, limit=pagination.limit, offset=pagination.offset),
    )


@router.get(
    "/{voice_id}", response_model=VoiceResponse, responses=_ERRORS, summary="Get one voice profile"
)
def get_voice(voice_id: str, service: VoiceServiceDep, settings: SettingsDep) -> VoiceResponse:
    return _to_response(service.get(voice_id), settings.api_v1_prefix)


@router.get(
    "/{voice_id}/sample",
    responses={200: {"content": {"audio/wav": {}}}, **_ERRORS},
    summary="Download the stored reference clip",
    response_class=FileResponse,
)
def get_voice_sample(voice_id: str, service: VoiceServiceDep) -> FileResponse:
    """Serve the reference audio through the API, never as a static mount.

    Keeps the on-disk layout private and gives per-request authorization a
    place to live once accounts exist.
    """
    path = service.reference_file(voice_id)
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"{voice_id}-reference.wav",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete(
    "/{voice_id}",
    response_model=DeletedResponse,
    responses=_ERRORS,
    summary="Delete a voice, its reference audio and all of its generations",
)
def delete_voice(voice_id: str, request: Request, service: VoiceServiceDep) -> DeletedResponse:
    deleted_id = service.delete(voice_id, actor=client_key(request))
    return DeletedResponse(id=deleted_id)
