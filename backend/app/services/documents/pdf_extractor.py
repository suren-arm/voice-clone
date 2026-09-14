"""PDF parsing via ``pypdf`` -- a maintained, actively-developed library.

No custom PDF parser: ``pypdf`` (BSD-3, the maintained successor to PyPDF2)
handles the container format, encryption and text extraction; this module
only adds the application's own validation, page-based section splitting and
scanned-PDF detection on top.
"""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf._encryption import PasswordType
from pypdf.errors import PdfReadError

from app.core.errors import DocumentValidationError, ScannedDocumentError
from app.services.documents.base import ExtractedDocument, ExtractedSection

#: Real PDFs may have a few junk bytes before the header (some generators,
#: and any file with a prepended comment), but the marker must appear near
#: the start -- never trust the ".pdf" filename/extension alone.
_HEADER_SEARCH_WINDOW = 1024

#: A page whose extracted text has fewer non-whitespace characters than this
#: is treated as (very likely) a scanned image with no text layer.
_MIN_CHARS_PER_PAGE_TO_COUNT = 10
#: If fewer than this fraction of pages clear the per-page threshold above,
#: the whole document is reported as scanned rather than silently returning
#: a near-empty result.
_MIN_USABLE_PAGE_FRACTION = 0.1
#: A page's first line is treated as a best-effort heading only if it is
#: short and does not read like a finished sentence -- never presented as a
#: guaranteed table of contents.
_MAX_HEADING_CHARS = 90
_SENTENCE_ENDINGS = (".", "!", "?", "։", ";", ",", ":")


def _guess_heading(page_text: str) -> str | None:
    first_line = page_text.strip().splitlines()[0].strip() if page_text.strip() else ""
    if not first_line or len(first_line) > _MAX_HEADING_CHARS:
        return None
    if first_line.endswith(_SENTENCE_ENDINGS):
        return None
    return first_line


def _extract_title(reader: PdfReader) -> str | None:
    try:
        metadata_title = reader.metadata.title if reader.metadata else None
    except Exception:  # noqa: BLE001 - a malformed /Info dict must not break extraction
        metadata_title = None
    return metadata_title.strip() if metadata_title and metadata_title.strip() else None


class PdfDocumentExtractor:
    """Validates a PDF and extracts its text, one section per page."""

    def extract(
        self,
        data: bytes,
        *,
        source_type: str,
        max_pages: int,
        original_filename: str | None = None,
        source_url: str | None = None,
    ) -> ExtractedDocument:
        if not data:
            raise DocumentValidationError("No PDF data was received.")
        if b"%PDF-" not in data[:_HEADER_SEARCH_WINDOW]:
            raise DocumentValidationError(
                "This file does not look like a PDF (missing the %PDF- header)."
            )

        try:
            reader = PdfReader(io.BytesIO(data))
        except PdfReadError as exc:
            raise DocumentValidationError(f"Could not read this PDF: {exc}") from exc

        if reader.is_encrypted:
            result = reader.decrypt("")
            if result == PasswordType.NOT_DECRYPTED:
                raise DocumentValidationError(
                    "This PDF is password-protected and cannot be processed."
                )

        try:
            page_count = len(reader.pages)
        except PdfReadError as exc:
            raise DocumentValidationError(f"Could not read this PDF's pages: {exc}") from exc

        if page_count == 0:
            raise DocumentValidationError("This PDF has no pages.")
        if page_count > max_pages:
            raise DocumentValidationError(
                f"This PDF has {page_count} pages; the limit is {max_pages}. "
                "Split it into smaller files, or narrate it in a different tool.",
                details={"pageCount": page_count, "maxPages": max_pages},
            )

        sections: list[ExtractedSection] = []
        usable_pages = 0
        for i, page in enumerate(reader.pages):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:  # noqa: BLE001 - one malformed page must not fail the whole book
                text = ""
            if len(text.replace(" ", "").replace("\n", "")) >= _MIN_CHARS_PER_PAGE_TO_COUNT:
                usable_pages += 1
            sections.append(
                ExtractedSection(index=i, text=text, title=_guess_heading(text), page_number=i + 1)
            )

        if usable_pages / page_count < _MIN_USABLE_PAGE_FRACTION:
            raise ScannedDocumentError(
                "This PDF appears to contain scanned pages and does not have extractable text.",
                details={"pageCount": page_count, "usablePages": usable_pages},
            )

        title = _extract_title(reader) or (sections[0].title if sections else None)

        return ExtractedDocument(
            title=title,
            source_type=source_type,
            sections=sections,
            source_url=source_url,
            original_filename=original_filename,
            page_count=page_count,
            is_scanned=False,
        )
