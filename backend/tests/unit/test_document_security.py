"""SSRF-safe URL validation and fetching.

Real DNS resolution is exercised against real public hostnames (this sandbox
has network access for plain DNS lookups) so the actual SSRF-relevant code
path runs end to end, but every actual data transfer is intercepted with
``httpx.MockTransport`` -- no test depends on a real website's content or
uptime.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.errors import RemoteFetchError, UnsupportedUrlError
from app.services.documents.security import fetch_url_safely, validate_public_url

# -- syntax / scheme ----------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "http://",
        "ftp://example.com/file.pdf",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://user:pass@example.com/",
        "",
    ],
)
def test_rejects_malformed_or_unsupported_urls(url: str):
    with pytest.raises(UnsupportedUrlError, match="Invalid URL"):
        validate_public_url(url)


# -- SSRF: private/local/metadata targets --------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://localhost:8000/",
        "http://127.0.0.1/",
        "http://127.0.0.1:9999/x",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata (link-local)
        "http://10.0.0.5/",
        "http://172.16.0.5/",
        "http://192.168.1.5/",
        "http://[fd00::1]/",  # IPv6 unique local (private)
    ],
)
def test_blocks_private_and_local_targets(url: str):
    with pytest.raises(UnsupportedUrlError, match="private, local"):
        validate_public_url(url)


def test_allows_a_real_public_hostname():
    # Only proves DNS resolves to a public address -- no data is fetched here.
    validate_public_url("https://example.com/")


# -- fetch mechanics: redirects, size cap, timeouts ----------------------------


def _handler(response_map):
    def handler(request: httpx.Request) -> httpx.Response:
        return response_map[str(request.url)]

    return handler


def test_fetch_follows_and_revalidates_redirects():
    responses = {
        "https://example.com/start": httpx.Response(
            302, headers={"Location": "https://example.com/final"}
        ),
        "https://example.com/final": httpx.Response(
            200, headers={"Content-Type": "text/html"}, content=b"<html>ok</html>"
        ),
    }
    transport = httpx.MockTransport(_handler(responses))
    result = fetch_url_safely(
        "https://example.com/start",
        max_bytes=1_000_000,
        connect_timeout=2,
        read_timeout=5,
        max_redirects=3,
        transport=transport,
    )
    assert result.content == b"<html>ok</html>"
    assert result.final_url == "https://example.com/final"


def test_fetch_blocks_a_redirect_into_a_private_target():
    responses = {
        "https://example.com/start": httpx.Response(
            302, headers={"Location": "http://127.0.0.1:9999/internal"}
        ),
    }
    transport = httpx.MockTransport(_handler(responses))
    with pytest.raises(UnsupportedUrlError, match="private, local"):
        fetch_url_safely(
            "https://example.com/start",
            max_bytes=1_000_000,
            connect_timeout=2,
            read_timeout=5,
            max_redirects=3,
            transport=transport,
        )


def test_fetch_enforces_redirect_loop_cap():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": str(request.url)})

    transport = httpx.MockTransport(handler)
    with pytest.raises(RemoteFetchError, match="Too many redirects"):
        fetch_url_safely(
            "https://example.com/loop",
            max_bytes=1_000_000,
            connect_timeout=2,
            read_timeout=5,
            max_redirects=2,
            transport=transport,
        )


def test_fetch_enforces_max_bytes_via_content_length():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/pdf", "Content-Length": "999999999"},
            content=b"x" * 10,
        )

    transport = httpx.MockTransport(handler)
    with pytest.raises(RemoteFetchError, match="limit"):
        fetch_url_safely(
            "https://example.com/huge.pdf",
            max_bytes=1024,
            connect_timeout=2,
            read_timeout=5,
            max_redirects=3,
            transport=transport,
        )


def test_fetch_enforces_max_bytes_while_streaming_even_without_content_length():
    """A server that omits/understates Content-Length must not bypass the cap."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"y" * 5000)

    transport = httpx.MockTransport(handler)
    with pytest.raises(RemoteFetchError, match="limit"):
        fetch_url_safely(
            "https://example.com/page",
            max_bytes=1024,
            connect_timeout=2,
            read_timeout=5,
            max_redirects=3,
            transport=transport,
        )


def test_fetch_reports_non_200_status_clearly():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    with pytest.raises(RemoteFetchError, match="HTTP 500"):
        fetch_url_safely(
            "https://example.com/broken",
            max_bytes=1_000_000,
            connect_timeout=2,
            read_timeout=5,
            max_redirects=3,
            transport=transport,
        )
