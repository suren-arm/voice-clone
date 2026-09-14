"""``/api/v1/books`` -- Book Reader: PDF upload / web-link ingestion, preview, narration.

    BookReaderController (this module)
            |
    DocumentService -- PdfDocumentExtractor / WebDocumentExtractor
            |
    Document + DocumentSection (persisted)
            |
    ReadingService (resolves a reading-range selection into text)
            |
    SpeechService.generate_for_book (the existing TTS pipeline)

See README.md's Book Reader section for the full architecture diagram and
why extraction, reading-range resolution and narration are three separate
services rather than one large one.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import (
    DocumentServiceDep,
    PaginationDep,
    ReadingServiceDep,
    SettingsDep,
    SpeechServiceDep,
    VoiceServiceDep,
    limit_book_ingest,
    limit_book_narrate,
)
from app.core.errors import PayloadTooLargeError
from app.core.rate_limit import client_key
from app.models.document import Document, DocumentSection
from app.schemas.common import DeletedResponse, ErrorResponse, Page, PageMeta
from app.schemas.document import (
    BookFromUrlRequest,
    BookNarrateRequest,
    BookNarrationResponse,
    DocumentResponse,
    DocumentSectionResponse,
    DocumentSectionSummary,
)
from app.services.documents import ReadingRange

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])

_ERRORS = {
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
}


def _document_response(document: Document, section_count: int) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        title=document.title,
        source_type=document.source_type,
        source_url=document.source_url,
        original_filename=document.original_filename,
        language=document.language,
        page_count=document.page_count,
        section_count=section_count,
        char_count=document.char_count,
        created_at=document.created_at,
    )


def _section_summary(section: DocumentSection) -> DocumentSectionSummary:
    return DocumentSectionSummary(
        index=section.index,
        title=section.title,
        page_number=section.page_number,
        char_count=section.char_count,
    )


async def _read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    """Stream the upload to memory, aborting as soon as the limit is passed.

    Mirrors ``voices.py``'s helper of the same name -- reading in chunks
    matters here for the same reason: a naive ``await upload.read()`` would
    happily buffer an oversized file before any size check could run.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                f"PDF exceeds the {max_bytes / 1024 / 1024:.0f} MB limit.",
                details={"maxBytes": max_bytes},
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Upload a PDF and extract its text",
    dependencies=[Depends(limit_book_ingest)],
)
async def upload_book(
    documents: DocumentServiceDep,
    settings: SettingsDep,
    file: UploadFile = File(..., description="A PDF file."),
) -> DocumentResponse:
    data = await _read_upload(file, settings.max_pdf_bytes)
    # PDF parsing is CPU-bound and can take real time on a large book; keep
    # it off the event loop like every other blocking call in this API.
    document = await run_in_threadpool(documents.create_from_upload, data, filename=file.filename)
    return _document_response(document, documents.section_count(document.id))


@router.post(
    "/from-url",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Fetch a public HTTP(S) link (PDF or article) and extract its text",
    dependencies=[Depends(limit_book_ingest)],
)
async def create_book_from_url(
    payload: BookFromUrlRequest,
    documents: DocumentServiceDep,
) -> DocumentResponse:
    document = await run_in_threadpool(documents.create_from_url, payload.url)
    return _document_response(document, documents.section_count(document.id))


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    responses=_ERRORS,
    summary="Get one extracted document's metadata",
)
def get_book(document_id: str, documents: DocumentServiceDep) -> DocumentResponse:
    document = documents.get(document_id)
    return _document_response(document, documents.section_count(document_id))


@router.get(
    "/{document_id}/sections",
    response_model=Page[DocumentSectionSummary],
    responses=_ERRORS,
    summary="Page through a document's sections (titles/lengths, no text)",
)
def list_sections(
    document_id: str, documents: DocumentServiceDep, pagination: PaginationDep
) -> Page[DocumentSectionSummary]:
    _document, items, total = documents.sections_page(
        document_id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[DocumentSectionSummary](
        items=[_section_summary(item) for item in items],
        meta=PageMeta(total=total, limit=pagination.limit, offset=pagination.offset),
    )


@router.get(
    "/{document_id}/sections/{index}",
    response_model=DocumentSectionResponse,
    responses=_ERRORS,
    summary="Get one section's full text (the extracted-text preview)",
)
def get_section(
    index: int, document_id: str, documents: DocumentServiceDep
) -> DocumentSectionResponse:
    _document, section = documents.section(document_id, index)
    return DocumentSectionResponse(
        index=section.index,
        title=section.title,
        page_number=section.page_number,
        char_count=section.char_count,
        text=section.text,
    )


@router.post(
    "/{document_id}/narrate",
    response_model=BookNarrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Narrate a selected reading range (page range, section, or the entire document)",
    dependencies=[Depends(limit_book_narrate)],
)
async def narrate_book(
    document_id: str,
    payload: BookNarrateRequest,
    request: Request,
    documents: DocumentServiceDep,
    reading: ReadingServiceDep,
    speech: SpeechServiceDep,
    voices: VoiceServiceDep,
    settings: SettingsDep,
) -> BookNarrationResponse:
    document = documents.get(document_id)
    range_ = ReadingRange(
        kind=payload.range.kind,
        from_page=payload.range.from_page,
        to_page=payload.range.to_page,
        section_index=payload.range.section_index,
    )
    text = reading.text_for_range(document, range_, max_chars=settings.max_book_narration_chars)

    voice = voices.get(payload.voice_id)
    profile = voices.profile_for(voice)
    result = await run_in_threadpool(
        speech.generate_for_book,
        text=text,
        language=payload.language,
        voice=voice,
        profile=profile,
        background_sound=payload.background_sound,
        background_volume=payload.background_volume,
        speed=payload.speed,
        actor=client_key(request),
    )
    generation = result.generation
    return BookNarrationResponse(
        generation_id=generation.id,
        document_id=document_id,
        range=payload.range,
        audio_url=f"{settings.api_v1_prefix}/generations/{generation.id}/audio",
        duration_seconds=generation.duration_seconds,
        notice=result.notice,
        background_applied=result.background_applied,
        background_notice=result.background_notice,
    )


@router.delete(
    "/{document_id}",
    response_model=DeletedResponse,
    responses=_ERRORS,
    summary="Delete an extracted document (its generated narrations are unaffected)",
)
def delete_book(document_id: str, documents: DocumentServiceDep) -> DeletedResponse:
    return DeletedResponse(id=documents.delete(document_id))
