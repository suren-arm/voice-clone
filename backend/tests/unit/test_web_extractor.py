"""WebDocumentExtractor -- HTML boilerplate removal and PDF-vs-HTML routing.

No real network: ``fetch_url_safely`` is patched where ``web_extractor``
imports it, and content-type/PDF-detection is tested directly against
constructed ``FetchedResource`` values.
"""

from __future__ import annotations

import app.services.documents.web_extractor as web_extractor_module
from app.services.documents.security import FetchedResource
from app.services.documents.web_extractor import WebDocumentExtractor

_REALISTIC_ARTICLE_HTML = b"""
<html><head><title>My Test Article</title></head>
<body>
<nav>Home | About | Contact | Subscribe | Login</nav>
<div class="cookie-banner">We use cookies. <button>Accept all</button></div>
<aside class="ads">Advertisement: Buy now!</aside>
<article>
<h1>The Great Forest Adventure</h1>
<p>Once upon a time, in a quiet town at the edge of a great forest, there lived a small rabbit
named Barnaby. He loved nothing more than exploring the tall grass near his burrow every
morning, watching the dew sparkle in the early sunlight before the rest of the world woke up.</p>
<p>One golden afternoon, while nibbling on a patch of sweet clover, Barnaby heard a rustle in
the bushes nearby. He froze, unsure whether to run or to look closer at the noise.</p>
<h2>Chapter Two: A New Friend</h2>
<p>Out from the bushes stepped a young fox named Rusty, his coat the color of autumn leaves. He
did not chase Barnaby. Instead he sat quietly, curious about the rabbit watching him.</p>
</article>
<div class="related-posts">Related: Top 10 forest animals</div>
<footer>Copyright 2026 Example Media. All rights reserved.</footer>
<script>gtag('config', 'UA-XXXX')</script>
</body></html>
"""


def test_strips_boilerplate_and_preserves_article_structure():
    extractor = WebDocumentExtractor()
    resource = FetchedResource(
        content=_REALISTIC_ARTICLE_HTML,
        content_type="text/html",
        final_url="https://example.com/story",
    )
    doc = extractor._extract_html(resource)

    assert doc.title == "The Great Forest Adventure"
    assert doc.source_type == "html_url"
    assert len(doc.sections) == 2
    assert doc.sections[0].title == "The Great Forest Adventure"
    assert "Barnaby" in doc.sections[0].text
    assert doc.sections[1].title == "Chapter Two: A New Friend"
    assert "Rusty" in doc.sections[1].text

    full_text = " ".join(s.text for s in doc.sections)
    for boilerplate in (
        "Home | About",
        "cookie",
        "Advertisement",
        "Related:",
        "Copyright 2026",
        "gtag",
    ):
        assert boilerplate not in full_text


def test_single_paragraph_page_becomes_one_section():
    html = b"<html><body><article><p>Just one short paragraph of real content here, nothing else.</p></article></body></html>"
    extractor = WebDocumentExtractor()
    resource = FetchedResource(
        content=html, content_type="text/html", final_url="https://example.com/x"
    )
    doc = extractor._extract_html(resource)
    assert len(doc.sections) == 1


def test_is_pdf_detects_by_content_type():
    resource = FetchedResource(
        content=b"%PDF-1.4 ...", content_type="application/pdf", final_url="https://example.com/x"
    )
    assert WebDocumentExtractor._is_pdf(resource) is True


def test_is_pdf_detects_by_magic_bytes_despite_wrong_content_type():
    resource = FetchedResource(
        content=b"%PDF-1.4\n...",
        content_type="application/octet-stream",
        final_url="https://example.com/x",
    )
    assert WebDocumentExtractor._is_pdf(resource) is True


def test_is_pdf_false_for_html():
    resource = FetchedResource(
        content=b"<html></html>",
        content_type="text/html; charset=utf-8",
        final_url="https://example.com/x",
    )
    assert WebDocumentExtractor._is_pdf(resource) is False


def test_extract_routes_pdf_response_to_pdf_extractor(monkeypatch, english_pdf_bytes: bytes):
    fake_resource = FetchedResource(
        content=english_pdf_bytes,
        content_type="application/pdf",
        final_url="https://example.com/book.pdf",
    )
    monkeypatch.setattr(web_extractor_module, "fetch_url_safely", lambda *a, **k: fake_resource)
    doc = WebDocumentExtractor().extract(
        "https://example.com/book.pdf",
        max_bytes=1_000_000,
        max_pages=10,
        connect_timeout=2,
        read_timeout=5,
        max_redirects=3,
    )
    assert doc.source_type == "pdf_url"
    assert doc.page_count == 2


def test_extract_routes_html_response_to_html_extraction(monkeypatch):
    fake_resource = FetchedResource(
        content=_REALISTIC_ARTICLE_HTML,
        content_type="text/html",
        final_url="https://example.com/story",
    )
    monkeypatch.setattr(web_extractor_module, "fetch_url_safely", lambda *a, **k: fake_resource)
    doc = WebDocumentExtractor().extract(
        "https://example.com/story",
        max_bytes=1_000_000,
        max_pages=10,
        connect_timeout=2,
        read_timeout=5,
        max_redirects=3,
    )
    assert doc.source_type == "html_url"
    assert doc.title == "The Great Forest Adventure"
