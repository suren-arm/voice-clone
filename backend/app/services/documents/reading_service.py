"""Turns a reading-range selection into the text one narration call will speak.

Deliberately the only place that enforces ``max_book_narration_chars``: a
book can be hundreds of pages, but "Start Reading" always synthesizes one
bounded batch at a time (see README.md's Book Reader section for why -- a
Render CPU instance has a real request-timeout ceiling). Picking a smaller
range is the user's tool for working through a long book; there is no
separate chunking-across-requests machinery to keep in sync with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.errors import NotFoundError, ValidationError
from app.models.document import Document
from app.repositories.document_repo import DocumentSectionRepository

ReadingRangeKind = Literal["entire", "pages", "section"]


@dataclass(frozen=True)
class ReadingRange:
    kind: ReadingRangeKind
    from_page: int | None = None
    to_page: int | None = None
    section_index: int | None = None


class ReadingService:
    def __init__(self, sections: DocumentSectionRepository) -> None:
        self._sections = sections

    def text_for_range(self, document: Document, range_: ReadingRange, *, max_chars: int) -> str:
        if range_.kind == "entire":
            selected = self._sections.all_for_document(document.id)
        elif range_.kind == "pages":
            if document.page_count is None:
                raise ValidationError(
                    "This document has no page numbers to select a range from -- "
                    "use 'Entire Article' or 'Selected Section' instead."
                )
            if (
                range_.from_page is None
                or range_.to_page is None
                or range_.from_page < 1
                or range_.to_page < range_.from_page
            ):
                raise ValidationError("Invalid page range.")
            selected = self._sections.in_page_range(
                document.id, from_page=range_.from_page, to_page=range_.to_page
            )
            if not selected:
                raise ValidationError(
                    f"No pages found in range {range_.from_page}-{range_.to_page}."
                )
        elif range_.kind == "section":
            if range_.section_index is None:
                raise ValidationError("A section index is required for this range type.")
            section = self._sections.by_index(document.id, range_.section_index)
            if section is None:
                raise NotFoundError(f"Section {range_.section_index} was not found.")
            selected = [section]
        else:  # pragma: no cover - Literal type + schema validation make this unreachable
            raise ValidationError(f"Unknown reading range kind: {range_.kind!r}")

        text = "\n\n".join(section.text for section in selected if section.text.strip())
        if not text.strip():
            raise ValidationError("The selected range has no readable text.")
        if len(text) > max_chars:
            raise ValidationError(
                f"The selected range is {len(text)} characters; one narration request is "
                f"limited to {max_chars}. Choose a smaller page range or section.",
                details={"chars": len(text), "maxChars": max_chars},
            )
        return text
