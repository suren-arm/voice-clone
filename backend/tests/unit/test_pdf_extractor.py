"""PdfDocumentExtractor -- real PDFs built with fpdf2, no mocking of pypdf itself."""

from __future__ import annotations

import pytest

from app.core.errors import DocumentValidationError, ScannedDocumentError
from app.services.documents.pdf_extractor import PdfDocumentExtractor

extractor = PdfDocumentExtractor()


def test_extracts_english_text_per_page(english_pdf_bytes: bytes):
    doc = extractor.extract(english_pdf_bytes, source_type="pdf_upload", max_pages=10)
    assert doc.page_count == 2
    assert len(doc.sections) == 2
    assert "fox and a rabbit" in doc.sections[0].text
    assert doc.sections[0].page_number == 1
    assert doc.sections[1].page_number == 2
    assert doc.is_scanned is False


def test_extracts_armenian_text_correctly(armenian_pdf_bytes: bytes):
    """The exact regression this feature exists to prevent: mojibake/'?????'."""
    doc = extractor.extract(armenian_pdf_bytes, source_type="pdf_upload", max_pages=10)
    assert "Մի անգամ մի փոքրիկ քաղաքում ապրում էր մի աղջիկ" in doc.sections[0].text
    assert "?" * 4 not in doc.sections[0].text
    # No mangled replacement characters anywhere in the extracted text.
    assert "�" not in doc.sections[0].text


def test_extracts_mixed_language_pdf_without_corruption(mixed_language_pdf_bytes: bytes):
    doc = extractor.extract(mixed_language_pdf_bytes, source_type="pdf_upload", max_pages=10)
    assert "fox and a rabbit" in doc.sections[0].text
    assert "Նա հանդիպեց մի սկյուռիկի անտառում" in doc.sections[1].text


def test_guesses_a_heading_from_the_first_short_line(english_pdf_bytes: bytes):
    doc = extractor.extract(english_pdf_bytes, source_type="pdf_upload", max_pages=10)
    assert doc.sections[0].title == "Chapter One"
    assert doc.sections[1].title == "Chapter Two"
    assert doc.title == "Chapter One"


def test_rejects_encrypted_pdf(encrypted_pdf_bytes: bytes):
    with pytest.raises(DocumentValidationError, match="password-protected"):
        extractor.extract(encrypted_pdf_bytes, source_type="pdf_upload", max_pages=10)


def test_detects_scanned_pdf_with_no_text_layer(scanned_pdf_bytes: bytes):
    with pytest.raises(ScannedDocumentError, match="scanned pages"):
        extractor.extract(scanned_pdf_bytes, source_type="pdf_upload", max_pages=10)


def test_rejects_non_pdf_data():
    with pytest.raises(DocumentValidationError, match="does not look like a PDF"):
        extractor.extract(
            b"this is definitely not a pdf file", source_type="pdf_upload", max_pages=10
        )


def test_rejects_empty_data():
    with pytest.raises(DocumentValidationError, match="No PDF data"):
        extractor.extract(b"", source_type="pdf_upload", max_pages=10)


def test_enforces_max_pages(english_pdf_bytes: bytes):
    with pytest.raises(DocumentValidationError, match="the limit is 1"):
        extractor.extract(english_pdf_bytes, source_type="pdf_upload", max_pages=1)


def test_does_not_trust_pdf_extension_alone():
    """A renamed non-PDF file must still be rejected on real content, not the filename."""
    with pytest.raises(DocumentValidationError):
        extractor.extract(
            b"not a pdf", source_type="pdf_upload", max_pages=10, original_filename="totally-a.pdf"
        )
