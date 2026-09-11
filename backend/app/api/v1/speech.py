"""``/api/v1/speech`` -- synthesis, and ``/api/v1/generations`` -- history.

**Why the response is JSON with an ``audioUrl``, not ``audio/wav`` directly.**
Returning raw bytes is simpler for exactly one use case (generate and play
once). It loses everything else: the history list, the per-generation RTF and
watermark metadata the safety story depends on, and byte-range seeking in the
player. A JSON resource plus a cacheable, range-capable audio endpoint costs one
extra round trip and is what an Android/iOS client wants anyway.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from app.api.deps import (
    PaginationDep,
    SettingsDep,
    SpeechServiceDep,
    VoiceServiceDep,
    limit_speech,
)
from app.core.rate_limit import client_key
from app.models.generation import Generation
from app.schemas.common import DeletedResponse, ErrorResponse, Page, PageMeta
from app.schemas.speech import GenerationResponse, SpeechRequest

logger = logging.getLogger(__name__)

speech_router = APIRouter(prefix="/speech", tags=["speech"])
generations_router = APIRouter(prefix="/generations", tags=["generations"])

_ERRORS = {
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def _to_response(
    generation: Generation, prefix: str, notice: str | None = None
) -> GenerationResponse:
    return GenerationResponse(
        id=generation.id,
        voice_id=generation.voice_id,
        text=generation.text,
        language=generation.language,
        created_at=generation.created_at,
        audio_url=f"{prefix}/generations/{generation.id}/audio",
        duration_seconds=generation.duration_seconds,
        sample_rate=generation.sample_rate,
        size_bytes=generation.size_bytes,
        generation_seconds=generation.generation_seconds,
        real_time_factor=generation.real_time_factor,
        engine=generation.engine,
        watermarked=generation.watermarked,
        experimental=generation.experimental,
        notice=notice,
    )


@speech_router.post(
    "",
    response_model=GenerationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Generate speech in a cloned voice",
    dependencies=[Depends(limit_speech)],
)
async def generate_speech(
    payload: SpeechRequest,
    request: Request,
    speech: SpeechServiceDep,
    voices: VoiceServiceDep,
    settings: SettingsDep,
) -> GenerationResponse:
    voice = voices.get(payload.voice_id)
    profile = voices.profile_for(voice)
    result = await run_in_threadpool(
        speech.generate, payload, voice, profile=profile, actor=client_key(request)
    )
    return _to_response(result.generation, settings.api_v1_prefix, result.notice)


@generations_router.get("", response_model=Page[GenerationResponse], summary="List generated audio")
def list_generations(
    speech: SpeechServiceDep,
    settings: SettingsDep,
    pagination: PaginationDep,
    voice_id: str | None = Query(None, alias="voiceId"),
) -> Page[GenerationResponse]:
    items, total = speech.list(voice_id=voice_id, limit=pagination.limit, offset=pagination.offset)
    return Page[GenerationResponse](
        items=[_to_response(item, settings.api_v1_prefix) for item in items],
        meta=PageMeta(total=total, limit=pagination.limit, offset=pagination.offset),
    )


@generations_router.get(
    "/{generation_id}",
    response_model=GenerationResponse,
    responses=_ERRORS,
    summary="Get one generation",
)
def get_generation(
    generation_id: str, speech: SpeechServiceDep, settings: SettingsDep
) -> GenerationResponse:
    return _to_response(speech.get(generation_id), settings.api_v1_prefix)


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
_HTTP_416 = 416  # Starlette renamed its constant; spell it numerically.


@generations_router.get(
    "/{generation_id}/audio",
    responses={200: {"content": {"audio/wav": {}}}, 206: {"content": {"audio/wav": {}}}, **_ERRORS},
    summary="Stream or download generated audio",
    response_class=FileResponse,
)
def get_generation_audio(
    generation_id: str,
    request: Request,
    speech: SpeechServiceDep,
    download: bool = Query(False, description="Force a download instead of inline playback."),
) -> Response:
    """Serve WAV with byte-range support so ``<audio>`` can seek.

    ``FileResponse`` does not implement ranges, and Safari refuses to scrub a
    media element that answers a Range request with a full 200. Hence the
    explicit handling below.
    """
    generation, path = speech.audio_file(generation_id)
    disposition = "attachment" if download else "inline"
    filename = f"{generation.id}.wav"
    size = path.stat().st_size
    headers = {
        "Content-Disposition": f'{disposition}; filename="{filename}"',
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=86400",
        "X-Content-Type-Options": "nosniff",
    }

    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(path, media_type="audio/wav", headers=headers)

    match = _RANGE_RE.match(range_header.strip())
    if not match:
        return FileResponse(path, media_type="audio/wav", headers=headers)

    start_raw, end_raw = match.groups()
    if start_raw:
        start = int(start_raw)
        end = int(end_raw) if end_raw else size - 1
    else:
        # Suffix range: "bytes=-500" means the last 500 bytes.
        if not end_raw:
            return FileResponse(path, media_type="audio/wav", headers=headers)
        start = max(0, size - int(end_raw))
        end = size - 1

    if start >= size:
        return Response(
            status_code=_HTTP_416,
            headers={"Content-Range": f"bytes */{size}"},
        )
    end = min(end, size - 1)
    with Path(path).open("rb") as handle:
        handle.seek(start)
        chunk = handle.read(end - start + 1)

    headers |= {
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Content-Length": str(len(chunk)),
    }
    return Response(
        content=chunk,
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type="audio/wav",
        headers=headers,
    )


@generations_router.delete(
    "/{generation_id}",
    response_model=DeletedResponse,
    responses=_ERRORS,
    summary="Delete a generation",
)
def delete_generation(
    generation_id: str, request: Request, speech: SpeechServiceDep
) -> DeletedResponse:
    return DeletedResponse(id=speech.delete(generation_id, actor=client_key(request)))
