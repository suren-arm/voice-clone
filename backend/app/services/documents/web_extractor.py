"""HTTP(S) link ingestion: fetch, decide PDF vs HTML, extract either way.

All outbound network access goes through :mod:`security` (SSRF-safe fetch) --
this module never imports ``httpx`` or touches a socket directly, and
:func:`trafilatura.extract` is always called with *already-fetched* content,
never given a bare URL to fetch itself, so no code path can bypass the SSRF
guard.
"""

from __future__ import annotations

import trafilatura

from app.core.errors import DocumentValidationError
from app.services.documents.base import ExtractedDocument, ExtractedSection
from app.services.documents.pdf_extractor import PdfDocumentExtractor
from app.services.documents.security import FetchedResource, fetch_url_safely, validate_public_url

#: A response is treated as a PDF if either the declared content-type says so
#: (may be missing or wrong -- some servers mislabel), or the body itself
#: starts with the real PDF magic bytes. Never trust ".pdf" in the URL alone.
_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}

#: A line is a heading candidate under the same shape rule the PDF extractor
#: uses: short, and not already a finished sentence.
_MAX_HEADING_CHARS = 90
_SENTENCE_ENDINGS = (".", "!", "?", "։", ";", ",", ":")


def _looks_like_heading(line: str) -> bool:
    return bool(line) and len(line) <= _MAX_HEADING_CHARS and not line.endswith(_SENTENCE_ENDINGS)


def _split_into_sections(body_text: str) -> list[ExtractedSection]:
    """Group trafilatura's line-per-block output into heading-delimited sections.

    trafilatura's plain-text output puts each extracted block (heading or
    paragraph) on its own line. A short, unpunctuated line is treated as a
    heading and starts a new section; anything else is a paragraph appended
    to the current one. When no line ever looks like a heading (common for a
    single-paragraph page, or a page trafilatura judged as one content block),
    the whole thing becomes exactly one section -- "Entire Article" is then
    the only sensible reading-range option, which is the honest outcome
    rather than a fabricated chapter split.
    """
    lines = [line.strip() for line in body_text.split("\n") if line.strip()]
    if not lines:
        return []

    sections: list[ExtractedSection] = []
    current_title: str | None = None
    current_paragraphs: list[str] = []

    def flush() -> None:
        if not current_paragraphs:
            return
        sections.append(
            ExtractedSection(
                index=len(sections),
                text="\n\n".join(current_paragraphs),
                title=current_title,
            )
        )

    for line in lines:
        if _looks_like_heading(line) and current_paragraphs:
            flush()
            current_paragraphs = []
            current_title = line
        elif _looks_like_heading(line) and not current_paragraphs and current_title is None:
            current_title = line
        else:
            current_paragraphs.append(line)
    flush()

    return sections or [ExtractedSection(index=0, text=body_text.strip())]


class WebDocumentExtractor:
    """Fetches a URL, decides PDF vs HTML from the real response, extracts either way."""

    def __init__(self, pdf_extractor: PdfDocumentExtractor | None = None) -> None:
        self._pdf_extractor = pdf_extractor or PdfDocumentExtractor()

    def extract(
        self,
        url: str,
        *,
        max_bytes: int,
        max_pages: int,
        connect_timeout: float,
        read_timeout: float,
        max_redirects: int,
    ) -> ExtractedDocument:
        # Fails fast with a friendly message for a malformed/blocked URL
        # before any network access is attempted.
        validate_public_url(url)

        resource = fetch_url_safely(
            url,
            max_bytes=max_bytes,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            max_redirects=max_redirects,
        )

        if self._is_pdf(resource):
            return self._pdf_extractor.extract(
                resource.content,
                source_type="pdf_url",
                max_pages=max_pages,
                source_url=resource.final_url,
            )
        return self._extract_html(resource)

    @staticmethod
    def _is_pdf(resource: FetchedResource) -> bool:
        if resource.content_type.lower() in _PDF_CONTENT_TYPES:
            return True
        return resource.content[:1024].find(b"%PDF-") != -1

    def _extract_html(self, resource: FetchedResource) -> ExtractedDocument:
        try:
            html_text = resource.content.decode("utf-8")
        except UnicodeDecodeError:
            html_text = resource.content.decode("utf-8", errors="replace")

        extracted = trafilatura.bare_extraction(
            html_text, url=resource.final_url, with_metadata=True
        )
        metadata = extracted.as_dict() if extracted else None
        if not metadata or not (metadata.get("text") or "").strip():
            raise DocumentValidationError("Could not find readable article content on this page.")

        # A second call for the line-per-block layout _split_into_sections
        # needs -- bare_extraction's dict form flattens everything into one
        # blob (see module docstring in reading_service.py for why this is a
        # deliberate two-pass approach rather than parsing bare_extraction's
        # internal lxml tree directly, which is not a stable public API).
        structured_text = (
            trafilatura.extract(
                html_text, url=resource.final_url, output_format="txt", with_metadata=False
            )
            or metadata["text"]
        )

        sections = _split_into_sections(structured_text)
        if not sections:
            raise DocumentValidationError("Could not find readable article content on this page.")

        return ExtractedDocument(
            title=(metadata.get("title") or "").strip() or None,
            source_type="html_url",
            sections=sections,
            source_url=resource.final_url,
            page_count=None,
            is_scanned=False,
        )
