"""Data access for extracted Book Reader documents."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentSection


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, document_id: str) -> Document | None:
        return self.session.get(Document, document_id)

    def add(self, document: Document) -> Document:
        self.session.add(document)
        self.session.flush()
        return document

    def delete(self, document: Document) -> None:
        self.session.delete(document)
        self.session.flush()

    def delete_created_before(self, cutoff: datetime) -> int:
        stmt = select(Document).where(Document.created_at < cutoff)
        stale = list(self.session.scalars(stmt))
        for document in stale:
            self.session.delete(document)
        if stale:
            self.session.flush()
        return len(stale)


class DocumentSectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_all(self, sections: list[DocumentSection]) -> None:
        self.session.add_all(sections)
        self.session.flush()

    def count_for_document(self, document_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentSection)
            .where(DocumentSection.document_id == document_id)
        )
        return int(self.session.scalar(stmt) or 0)

    def page(
        self, document_id: str, *, limit: int, offset: int
    ) -> tuple[list[DocumentSection], int]:
        base = select(DocumentSection).where(DocumentSection.document_id == document_id)
        items = list(
            self.session.scalars(base.order_by(DocumentSection.index).limit(limit).offset(offset))
        )
        total = int(
            self.session.scalar(
                select(func.count())
                .select_from(DocumentSection)
                .where(DocumentSection.document_id == document_id)
            )
            or 0
        )
        return items, total

    def in_page_range(
        self, document_id: str, *, from_page: int, to_page: int
    ) -> list[DocumentSection]:
        stmt = (
            select(DocumentSection)
            .where(
                DocumentSection.document_id == document_id,
                DocumentSection.page_number.is_not(None),
                DocumentSection.page_number >= from_page,
                DocumentSection.page_number <= to_page,
            )
            .order_by(DocumentSection.index)
        )
        return list(self.session.scalars(stmt))

    def by_index(self, document_id: str, index: int) -> DocumentSection | None:
        stmt = select(DocumentSection).where(
            DocumentSection.document_id == document_id, DocumentSection.index == index
        )
        return self.session.scalar(stmt)

    def all_for_document(self, document_id: str) -> list[DocumentSection]:
        stmt = (
            select(DocumentSection)
            .where(DocumentSection.document_id == document_id)
            .order_by(DocumentSection.index)
        )
        return list(self.session.scalars(stmt))
