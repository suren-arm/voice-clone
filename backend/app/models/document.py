"""Book Reader ORM models: an extracted document and its ordered sections.

What is deliberately *not* stored here: the original PDF bytes (uploaded or
downloaded). Only the extracted text and enough structure to page through it
survives -- see ``services/documents/document_service.py``. That keeps this
feature from becoming a permanent copy of whatever the user pointed it at,
and sidesteps ever needing to re-parse (or re-fetch) a PDF later.

A ``DocumentSection`` is the one paging unit for both source types: one PDF
page for a PDF, one heading-delimited block for an HTML article (or the
whole article as a single section when no heading structure was found --
see ``services/documents/web_extractor.py``). Reading-range selection,
preview pagination and narration chunking all operate on this same list.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # "pdf_upload" | "pdf_url" | "html_url"
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Detected default; the reading/narration request can override it.
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_scanned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    sections: Mapped[list[DocumentSection]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentSection.index",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Document {self.id} {self.title!r} sections={len(self.sections)}>"


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Best-effort only -- see pdf_extractor.py / web_extractor.py. Never
    # presented as a guaranteed table of contents.
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # 1-based PDF page number this section corresponds to. Null for an HTML
    # section, which has no page concept.
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    document: Mapped[Document] = relationship(back_populates="sections")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<DocumentSection {self.document_id}#{self.index} page={self.page_number}>"
