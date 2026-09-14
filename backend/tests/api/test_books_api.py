"""``/api/v1/books`` -- end-to-end Book Reader API tests.

PDF upload uses real PDF bytes (see conftest.py's make_pdf_bytes fixtures).
URL ingestion mocks ``web_extractor.fetch_url_safely`` -- the one function
that touches the network -- so these tests need no real internet access and
never depend on an external site's uptime or content.
"""

from __future__ import annotations

import pytest

import app.services.documents.web_extractor as web_extractor_module
from app.services.documents.security import FetchedResource


def _default_voice(client, language="en"):
    """The built-in voice for ``language``, or a clear skip if espeak-ng is absent.

    Default voices are bootstrapped from espeak-ng at startup, so a host
    without it has none -- skip with a readable reason rather than letting
    ``next()`` raise a bare StopIteration that says nothing about why.
    """
    defaults = client.get("/api/v1/voices/defaults").json()
    voice = next((v for v in defaults if v["language"] == language), None)
    if voice is None:
        pytest.skip(f"no built-in {language} default voice (espeak-ng not installed?)")
    return voice


# -- PDF upload ---------------------------------------------------------------


def test_upload_pdf_extracts_and_returns_document(client, english_pdf_bytes: bytes):
    response = client.post(
        "/api/v1/books/upload",
        files={"file": ("story.pdf", english_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["sourceType"] == "pdf_upload"
    assert body["pageCount"] == 2
    assert body["sectionCount"] == 2
    assert body["language"] == "en"
    assert body["title"] == "Chapter One"


def test_upload_armenian_pdf_detects_armenian_language(client, armenian_pdf_bytes: bytes):
    response = client.post(
        "/api/v1/books/upload",
        files={"file": ("hy.pdf", armenian_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["language"] == "hy"


def test_upload_rejects_non_pdf_content(client):
    response = client.post(
        "/api/v1/books/upload",
        files={"file": ("fake.pdf", b"not a real pdf file", "application/pdf")},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "document_invalid"


def test_upload_rejects_encrypted_pdf(client, encrypted_pdf_bytes: bytes):
    response = client.post(
        "/api/v1/books/upload",
        files={"file": ("locked.pdf", encrypted_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 422, response.text
    assert "password-protected" in response.json()["error"]["message"]


def test_upload_rejects_scanned_pdf_with_clear_message(client, scanned_pdf_bytes: bytes):
    response = client.post(
        "/api/v1/books/upload",
        files={"file": ("scan.pdf", scanned_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error"]["code"] == "document_scanned"
    assert "scanned pages" in body["error"]["message"]


def test_upload_oversized_pdf_is_413(client, english_pdf_bytes: bytes):
    # Shrink the limit via the same Settings object the app already resolved
    # (the `client`/`app` fixtures construct it once per test via get_settings()).
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.max_pdf_bytes
    settings.max_pdf_bytes = 10
    try:
        response = client.post(
            "/api/v1/books/upload",
            files={"file": ("story.pdf", english_pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 413, response.text
        assert response.json()["error"]["code"] == "payload_too_large"
    finally:
        settings.max_pdf_bytes = original


# -- URL ingestion (mocked fetch) ----------------------------------------------


def test_from_url_rejects_private_target(client):
    response = client.post("/api/v1/books/from-url", json={"url": "http://127.0.0.1/internal"})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "unsupported_url"


def test_from_url_rejects_malformed_url(client):
    response = client.post("/api/v1/books/from-url", json={"url": "not a url"})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "unsupported_url"


def test_from_url_rejects_non_http_scheme(client):
    response = client.post("/api/v1/books/from-url", json={"url": "ftp://example.com/file"})
    assert response.status_code == 422, response.text


def test_from_url_ingests_a_remote_pdf(client, english_pdf_bytes: bytes, monkeypatch):
    fake = FetchedResource(
        content=english_pdf_bytes,
        content_type="application/pdf",
        final_url="https://example.com/book.pdf",
    )
    monkeypatch.setattr(web_extractor_module, "fetch_url_safely", lambda *a, **k: fake)

    response = client.post("/api/v1/books/from-url", json={"url": "https://example.com/book.pdf"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["sourceType"] == "pdf_url"
    assert body["sourceUrl"] == "https://example.com/book.pdf"
    assert body["pageCount"] == 2


def test_from_url_ingests_an_html_article(client, monkeypatch):
    html = (
        b"<html><body><article><h1>A Real Article</h1>"
        b"<p>This is a real paragraph of readable article content for the test.</p>"
        b"</article></body></html>"
    )
    fake = FetchedResource(
        content=html, content_type="text/html", final_url="https://example.com/story"
    )
    monkeypatch.setattr(web_extractor_module, "fetch_url_safely", lambda *a, **k: fake)

    response = client.post("/api/v1/books/from-url", json={"url": "https://example.com/story"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["sourceType"] == "html_url"
    assert body["title"] == "A Real Article"
    assert body["pageCount"] is None


# -- sections / preview ---------------------------------------------------------


def test_list_and_get_sections(client, english_pdf_bytes: bytes):
    document_id = client.post(
        "/api/v1/books/upload", files={"file": ("s.pdf", english_pdf_bytes, "application/pdf")}
    ).json()["id"]

    listing = client.get(f"/api/v1/books/{document_id}/sections")
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert len(items) == 2
    assert "text" not in items[0]  # summary only, never the full book in one response

    section = client.get(f"/api/v1/books/{document_id}/sections/0")
    assert section.status_code == 200, section.text
    assert "fox and a rabbit" in section.json()["text"]


def test_get_unknown_section_is_404(client, english_pdf_bytes: bytes):
    document_id = client.post(
        "/api/v1/books/upload", files={"file": ("s.pdf", english_pdf_bytes, "application/pdf")}
    ).json()["id"]
    response = client.get(f"/api/v1/books/{document_id}/sections/99")
    assert response.status_code == 404


def test_get_unknown_document_is_404(client):
    response = client.get("/api/v1/books/doc_doesnotexist000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


# -- narration ------------------------------------------------------------------


def test_narrate_entire_document_with_default_voice(client, english_pdf_bytes: bytes):
    document_id = client.post(
        "/api/v1/books/upload", files={"file": ("s.pdf", english_pdf_bytes, "application/pdf")}
    ).json()["id"]
    voice = _default_voice(client, "en")

    response = client.post(
        f"/api/v1/books/{document_id}/narrate",
        json={"voiceId": voice["id"], "language": "en", "range": {"kind": "entire"}},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["documentId"] == document_id
    assert body["generationId"]

    # The returned audio is a genuine, playable Generation via the existing
    # /generations endpoint -- no separate book-audio machinery.
    audio = client.get(body["audioUrl"])
    assert audio.status_code == 200


def test_narrate_a_page_range(client, english_pdf_bytes: bytes):
    document_id = client.post(
        "/api/v1/books/upload", files={"file": ("s.pdf", english_pdf_bytes, "application/pdf")}
    ).json()["id"]
    voice = _default_voice(client, "en")

    response = client.post(
        f"/api/v1/books/{document_id}/narrate",
        json={
            "voiceId": voice["id"],
            "language": "en",
            "range": {"kind": "pages", "fromPage": 2, "toPage": 2},
        },
    )
    assert response.status_code == 201, response.text


def test_narrate_a_single_section(client, english_pdf_bytes: bytes):
    document_id = client.post(
        "/api/v1/books/upload", files={"file": ("s.pdf", english_pdf_bytes, "application/pdf")}
    ).json()["id"]
    voice = _default_voice(client, "en")

    response = client.post(
        f"/api/v1/books/{document_id}/narrate",
        json={
            "voiceId": voice["id"],
            "language": "en",
            "range": {"kind": "section", "sectionIndex": 0},
        },
    )
    assert response.status_code == 201, response.text


def test_narrate_armenian_pdf_with_armenian_default_voice(client, armenian_pdf_bytes: bytes):
    document_id = client.post(
        "/api/v1/books/upload", files={"file": ("hy.pdf", armenian_pdf_bytes, "application/pdf")}
    ).json()["id"]
    voice = _default_voice(client, "hy")

    response = client.post(
        f"/api/v1/books/{document_id}/narrate",
        json={"voiceId": voice["id"], "language": "hy", "range": {"kind": "entire"}},
    )
    assert response.status_code == 201, response.text


def test_narrate_with_background_and_speed(client, english_pdf_bytes: bytes):
    document_id = client.post(
        "/api/v1/books/upload", files={"file": ("s.pdf", english_pdf_bytes, "application/pdf")}
    ).json()["id"]
    voice = _default_voice(client, "en")

    response = client.post(
        f"/api/v1/books/{document_id}/narrate",
        json={
            "voiceId": voice["id"],
            "language": "en",
            "range": {"kind": "entire"},
            "speed": 1.25,
            "backgroundSound": "calm",
            "backgroundVolume": 20,
        },
    )
    assert response.status_code == 201, response.text


def test_narrate_range_exceeding_char_budget_is_a_clear_422(
    client, english_pdf_bytes: bytes, monkeypatch
):
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.max_book_narration_chars
    settings.max_book_narration_chars = 5
    try:
        document_id = client.post(
            "/api/v1/books/upload", files={"file": ("s.pdf", english_pdf_bytes, "application/pdf")}
        ).json()["id"]
        voice = _default_voice(client, "en")
        response = client.post(
            f"/api/v1/books/{document_id}/narrate",
            json={"voiceId": voice["id"], "language": "en", "range": {"kind": "entire"}},
        )
        assert response.status_code == 422, response.text
        assert "smaller" in response.json()["error"]["message"]
    finally:
        settings.max_book_narration_chars = original


def test_narrate_invalid_page_range_shape_is_422(client, english_pdf_bytes: bytes):
    document_id = client.post(
        "/api/v1/books/upload", files={"file": ("s.pdf", english_pdf_bytes, "application/pdf")}
    ).json()["id"]
    voice = _default_voice(client, "en")
    response = client.post(
        f"/api/v1/books/{document_id}/narrate",
        json={"voiceId": voice["id"], "language": "en", "range": {"kind": "pages"}},
    )
    assert response.status_code == 422


# -- delete ---------------------------------------------------------------------


def test_delete_document_then_404(client, english_pdf_bytes: bytes):
    document_id = client.post(
        "/api/v1/books/upload", files={"file": ("s.pdf", english_pdf_bytes, "application/pdf")}
    ).json()["id"]
    deleted = client.delete(f"/api/v1/books/{document_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/api/v1/books/{document_id}")
    assert missing.status_code == 404
