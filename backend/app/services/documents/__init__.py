"""Book Reader document ingestion: PDF upload or a web link -> extracted text.

See ``document_service.py`` for the architecture overview.
"""

from __future__ import annotations

from app.services.documents.base import ExtractedDocument, ExtractedSection
from app.services.documents.document_service import DocumentService, cleanup_stale_documents
from app.services.documents.reading_service import ReadingRange, ReadingService

__all__ = [
    "DocumentService",
    "ExtractedDocument",
    "ExtractedSection",
    "ReadingRange",
    "ReadingService",
    "cleanup_stale_documents",
]
