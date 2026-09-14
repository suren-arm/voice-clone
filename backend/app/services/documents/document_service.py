"""Book Reader ingestion: PDF upload or a web link, in, ``Document`` out.

    BookReaderController (app/api/v1/books.py)
            |
    DocumentService (this module)
            |
    PdfDocumentExtractor / WebDocumentExtractor
            |
    ExtractedDocument (app/services/documents/base.py)
            |
    Document + DocumentSection (persisted)

Narration is a deliberately separate concern: this module never touches the
TTS engine, and ``ReadingService``/``SpeechService`` never touch a PDF
library or an HTTP client. See README.md's Book Reader architecture diagram.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DocumentNotFoundError, NotFoundError, PayloadTooLargeError
from app.core.security import is_safe_id, new_id, sanitize_display_name, sanitize_filename
from app.db.base import utcnow
from app.models.document import Document, DocumentSection
from app.repositories.document_repo import DocumentRepository, DocumentSectionRepository
from app.services.documents.base import ExtractedDocument
from app.services.documents.language import detect_language
from app.services.documents.pdf_extractor import PdfDocumentExtractor
from app.services.documents.web_extractor import WebDocumentExtractor

logger = logging.getLogger(__name__)


@dataclass
class DocumentService:
    session: Session
    settings: Settings

    def __post_init__(self) -> None:
        self.documents = DocumentRepository(self.session)
        self.sections = DocumentSectionRepository(self.session)
        self._pdf_extractor = PdfDocumentExtractor()
        self._web_extractor = WebDocumentExtractor(self._pdf_extractor)

    # -- ingest --------------------------------------------------------------
    def create_from_upload(self, data: bytes, *, filename: str | None) -> Document:
        if len(data) > self.settings.max_pdf_bytes:
            raise PayloadTooLargeError(
                f"PDF is {len(data) / 1024 / 1024:.1f} MB; the limit is "
                f"{self.settings.max_pdf_bytes / 1024 / 1024:.0f} MB.",
                details={"maxBytes": self.settings.max_pdf_bytes},
            )
        extracted = self._pdf_extractor.extract(
            data,
            source_type="pdf_upload",
            max_pages=self.settings.max_pdf_pages,
            original_filename=sanitize_filename(filename),
        )
        return self._persist(extracted)

    def create_from_url(self, url: str) -> Document:
        extracted = self._web_extractor.extract(
            url,
            max_bytes=self.settings.max_remote_download_bytes,
            max_pages=self.settings.max_pdf_pages,
            connect_timeout=self.settings.book_fetch_connect_timeout_seconds,
            read_timeout=self.settings.book_fetch_read_timeout_seconds,
            max_redirects=self.settings.book_fetch_max_redirects,
        )
        return self._persist(extracted)

    def _persist(self, extracted: ExtractedDocument) -> Document:
        document_id = new_id("doc")
        full_text = "\n\n".join(section.text for section in extracted.sections)
        language = detect_language(full_text)

        document = Document(
            id=document_id,
            title=sanitize_display_name(extracted.title) if extracted.title else None,
            source_type=extracted.source_type,
            source_url=extracted.source_url,
            original_filename=extracted.original_filename,
            language=language,
            page_count=extracted.page_count,
            char_count=extracted.char_count,
            is_scanned=extracted.is_scanned,
        )
        self.documents.add(document)
        self.sections.add_all(
            [
                DocumentSection(
                    document_id=document_id,
                    index=section.index,
                    title=sanitize_display_name(section.title) if section.title else None,
                    page_number=section.page_number,
                    text=section.text,
                    char_count=len(section.text),
                )
                for section in extracted.sections
            ]
        )
        logger.info(
            "Extracted document %s (%s, %d sections, %d chars, language=%s)",
            document_id,
            extracted.source_type,
            len(extracted.sections),
            extracted.char_count,
            language,
        )
        return document

    # -- read ------------------------------------------------------------
    def get(self, document_id: str) -> Document:
        if not is_safe_id(document_id, "doc"):
            raise DocumentNotFoundError(f"Document '{document_id}' was not found.")
        document = self.documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{document_id}' was not found.")
        return document

    def sections_page(
        self, document_id: str, *, limit: int, offset: int
    ) -> tuple[Document, list[DocumentSection], int]:
        document = self.get(document_id)
        items, total = self.sections.page(document_id, limit=limit, offset=offset)
        return document, items, total

    def section(self, document_id: str, index: int) -> tuple[Document, DocumentSection]:
        document = self.get(document_id)
        section = self.sections.by_index(document_id, index)
        if section is None:
            raise NotFoundError(f"Section {index} was not found in document '{document_id}'.")
        return document, section

    def section_count(self, document_id: str) -> int:
        return self.sections.count_for_document(document_id)

    # -- delete ------------------------------------------------------------
    def delete(self, document_id: str) -> str:
        document = self.get(document_id)
        self.documents.delete(document)
        return document_id


def cleanup_stale_documents(session: Session, settings: Settings) -> int:
    """Remove extracted documents older than the retention window.

    Called at startup (see ``app/main.py``), mirroring
    ``LocalStorage.cleanup_tmp()`` -- the Book Reader is not meant to be a
    permanent library, and the original PDF was never kept in the first
    place (see this module's docstring), so there is nothing else to clean
    up alongside the DB rows.
    """
    cutoff = utcnow() - timedelta(hours=settings.document_retention_hours)
    removed = DocumentRepository(session).delete_created_before(cutoff)
    if removed:
        logger.info("Cleaned up %d stale extracted document(s)", removed)
    return removed
