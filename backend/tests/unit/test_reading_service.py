"""ReadingService -- resolving a reading-range selection into narratable text.

Uses a fake section repository (same shape as DocumentSectionRepository) so
this stays a pure unit test with no database involved -- mirrors the
_FakeProvider pattern in test_ai_provider_registry.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.errors import NotFoundError, ValidationError
from app.services.documents.reading_service import ReadingRange, ReadingService


@dataclass
class _FakeSection:
    index: int
    text: str
    page_number: int | None = None


@dataclass
class _FakeDocument:
    id: str
    page_count: int | None


class _FakeSectionRepo:
    def __init__(self, sections: list[_FakeSection]) -> None:
        self._sections = sections

    def all_for_document(self, document_id: str) -> list[_FakeSection]:
        return list(self._sections)

    def in_page_range(
        self, document_id: str, *, from_page: int, to_page: int
    ) -> list[_FakeSection]:
        return [
            s for s in self._sections if s.page_number and from_page <= s.page_number <= to_page
        ]

    def by_index(self, document_id: str, index: int) -> _FakeSection | None:
        return next((s for s in self._sections if s.index == index), None)


def _sections() -> list[_FakeSection]:
    return [
        _FakeSection(index=0, text="Page one text.", page_number=1),
        _FakeSection(index=1, text="Page two text.", page_number=2),
        _FakeSection(index=2, text="Page three text.", page_number=3),
    ]


def test_entire_range_concatenates_all_sections():
    service = ReadingService(_FakeSectionRepo(_sections()))
    document = _FakeDocument(id="doc_x", page_count=3)
    text = service.text_for_range(document, ReadingRange(kind="entire"), max_chars=1000)
    assert "Page one" in text and "Page two" in text and "Page three" in text


def test_page_range_selects_only_requested_pages():
    service = ReadingService(_FakeSectionRepo(_sections()))
    document = _FakeDocument(id="doc_x", page_count=3)
    text = service.text_for_range(
        document, ReadingRange(kind="pages", from_page=2, to_page=2), max_chars=1000
    )
    assert text == "Page two text."


def test_page_range_out_of_bounds_raises():
    service = ReadingService(_FakeSectionRepo(_sections()))
    document = _FakeDocument(id="doc_x", page_count=3)
    with pytest.raises(ValidationError, match="No pages found"):
        service.text_for_range(
            document, ReadingRange(kind="pages", from_page=10, to_page=20), max_chars=1000
        )


def test_page_range_on_document_without_pages_raises():
    service = ReadingService(_FakeSectionRepo(_sections()))
    document = _FakeDocument(id="doc_x", page_count=None)
    with pytest.raises(ValidationError, match="no page numbers"):
        service.text_for_range(
            document, ReadingRange(kind="pages", from_page=1, to_page=2), max_chars=1000
        )


def test_section_range_selects_one_section():
    service = ReadingService(_FakeSectionRepo(_sections()))
    document = _FakeDocument(id="doc_x", page_count=3)
    text = service.text_for_range(
        document, ReadingRange(kind="section", section_index=1), max_chars=1000
    )
    assert text == "Page two text."


def test_unknown_section_index_raises_not_found():
    service = ReadingService(_FakeSectionRepo(_sections()))
    document = _FakeDocument(id="doc_x", page_count=3)
    with pytest.raises(NotFoundError):
        service.text_for_range(
            document, ReadingRange(kind="section", section_index=99), max_chars=1000
        )


def test_exceeding_max_chars_raises_with_a_clear_message():
    service = ReadingService(_FakeSectionRepo(_sections()))
    document = _FakeDocument(id="doc_x", page_count=3)
    with pytest.raises(ValidationError, match="Choose a smaller"):
        service.text_for_range(document, ReadingRange(kind="entire"), max_chars=5)


def test_blank_only_sections_raise_no_readable_text():
    service = ReadingService(_FakeSectionRepo([_FakeSection(index=0, text="   ", page_number=1)]))
    document = _FakeDocument(id="doc_x", page_count=1)
    with pytest.raises(ValidationError, match="no readable text"):
        service.text_for_range(document, ReadingRange(kind="entire"), max_chars=1000)
