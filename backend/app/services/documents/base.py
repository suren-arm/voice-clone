"""Provider-neutral in-memory document model.

Every extractor (:mod:`pdf_extractor`, :mod:`web_extractor`) returns exactly
this shape, whatever the source. :class:`~app.services.documents.document_service.DocumentService`
is the only thing that knows how to turn it into the persisted
``Document``/``DocumentSection`` rows -- extraction never touches the
database directly, and narration (:mod:`reading_service`) never touches a
PDF or an HTTP client directly. That separation is the point: a PDF parsing
bug cannot corrupt narration, and a narration change cannot need to know a
PDF library exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractedSection:
    """One page (PDF) or heading-delimited block (HTML article)."""

    index: int
    text: str
    title: str | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class ExtractedDocument:
    """What any extractor hands back, before persistence."""

    title: str | None
    source_type: str  # "pdf_upload" | "pdf_url" | "html_url"
    sections: list[ExtractedSection] = field(default_factory=list)
    source_url: str | None = None
    original_filename: str | None = None
    page_count: int | None = None
    is_scanned: bool = False

    @property
    def char_count(self) -> int:
        return sum(len(section.text) for section in self.sections)
