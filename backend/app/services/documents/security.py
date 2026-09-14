"""SSRF-safe URL validation and fetching for the Book Reader's "Web Link" input.

This is the one place in the app that turns a user-supplied string into an
outbound HTTP request, so it carries the full defensive burden alone --
:mod:`web_extractor` never touches ``httpx``/``socket`` directly.

Defence in depth, in order:

1. **Syntax**: only ``http``/``https``, a real hostname, no embedded
   credentials (``user:pass@host`` is a classic confusion vector).
2. **DNS resolution check**: every IP address the hostname resolves to must
   be a public, routable address -- not loopback, private, link-local,
   multicast, reserved or unspecified. This blocks ``localhost``,
   ``127.0.0.1``, ``::1``, RFC 1918/4193 ranges, and cloud metadata
   endpoints (``169.254.169.254`` and friends all fall in link-local/ULA
   ranges the stdlib ``ipaddress`` module already classifies correctly).
3. **No redirect is trusted blind**: redirects are followed manually, one hop
   at a time, and each target is re-validated against steps 1-2 before it is
   fetched -- a public URL that redirects to an internal one is refused
   exactly like requesting the internal one directly.
4. **Bounded resources**: separate connect/read timeouts, a hard cap on
   redirect count, and a byte cap enforced while *streaming* the body (not
   trusted from a ``Content-Length`` header, which a malicious or
   misconfigured server can simply omit or lie about).

**Known, documented limitation.** Step 2 resolves the hostname once, up
front; the actual TCP connection performs its own DNS resolution moments
later. An adversary controlling DNS for the target hostname could in
principle answer the first lookup with a public IP and the second with a
private one ("DNS rebinding"). Closing this completely needs a transport
that pins the exact validated IP for the connection, which httpx does not
expose a simple hook for. This mitigates the overwhelmingly common SSRF
cases (literal internal addresses, `localhost`, known metadata hostnames)
correctly; a deployment with a stricter threat model should pair this with
network-level egress control (a firewall or forward proxy) rather than rely
on application-layer checks alone.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.core.errors import RemoteFetchError, UnsupportedUrlError

ALLOWED_SCHEMES = {"http", "https"}

_INVALID_URL_MESSAGE = "Invalid URL. Only public HTTP and HTTPS links are supported."
_BLOCKED_TARGET_MESSAGE = (
    "This URL points to a private, local, or otherwise disallowed network address "
    "and cannot be fetched."
)


def _is_public_ip(ip_str: str) -> bool:
    addr = ipaddress.ip_address(ip_str)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _validate_syntax(url: str) -> str:
    """Reject malformed URLs and anything but a plain http(s) origin.

    Returns the URL unchanged (not normalised) -- callers that need the
    final, possibly-redirected URL use whatever the last validated hop was.
    """
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise UnsupportedUrlError(_INVALID_URL_MESSAGE) from exc

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsupportedUrlError(_INVALID_URL_MESSAGE)
    if not parts.hostname:
        raise UnsupportedUrlError(_INVALID_URL_MESSAGE)
    if parts.username or parts.password:
        # Embedded credentials are never needed for a public book/article and
        # are a classic trick for confusing naive host-parsing logic.
        raise UnsupportedUrlError(_INVALID_URL_MESSAGE)
    return url


def _validate_target(hostname: str) -> None:
    """Resolve ``hostname`` and refuse it if any address is non-public."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsupportedUrlError(f"Could not resolve host '{hostname}'.") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UnsupportedUrlError(f"Could not resolve host '{hostname}'.")
    for address in addresses:
        if not _is_public_ip(address):
            raise UnsupportedUrlError(_BLOCKED_TARGET_MESSAGE)


def validate_public_url(url: str) -> str:
    """Full pre-flight check: syntax + DNS-resolved target. Raises on failure."""
    validated = _validate_syntax(url)
    hostname = urlsplit(validated).hostname
    assert hostname is not None  # guaranteed by _validate_syntax
    _validate_target(hostname)
    return validated


@dataclass(frozen=True)
class FetchedResource:
    content: bytes
    content_type: str
    final_url: str


def fetch_url_safely(
    url: str,
    *,
    max_bytes: int,
    connect_timeout: float,
    read_timeout: float,
    max_redirects: int,
    transport: httpx.BaseTransport | None = None,
) -> FetchedResource:
    """Fetch ``url``, following redirects manually and re-validating each hop.

    Raises :class:`UnsupportedUrlError` for anything that fails the SSRF
    checks (including a redirect into a blocked target) and
    :class:`RemoteFetchError` for network/timeout/size failures once past
    those checks.

    ``transport`` is exposed purely for tests (``httpx.MockTransport``) so
    the DNS/SSRF checks above run for real against a real public hostname
    while the actual response is deterministic and offline -- production
    code never passes it, and the default (``None``) uses a real connection.
    """
    current = validate_public_url(url)
    timeout = httpx.Timeout(
        connect=connect_timeout, read=read_timeout, write=read_timeout, pool=connect_timeout
    )

    with httpx.Client(follow_redirects=False, timeout=timeout, transport=transport) as client:
        for _ in range(max_redirects + 1):
            try:
                with client.stream(
                    "GET",
                    current,
                    headers={"User-Agent": "VoiceStoryStudio-BookReader/1.0"},
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise RemoteFetchError(
                                "The server sent a redirect with no destination."
                            )
                        # Resolve a relative Location against the current URL,
                        # then re-run the full SSRF check on the *resolved*
                        # absolute URL -- a relative redirect must not skip
                        # validation, and neither may a redirect to a
                        # different, disallowed host.
                        next_url = str(httpx.URL(current).join(location))
                        current = validate_public_url(next_url)
                        continue

                    if response.status_code != httpx.codes.OK:
                        raise RemoteFetchError(
                            f"The server responded with HTTP {response.status_code}."
                        )

                    content_type = response.headers.get("content-type", "").split(";")[0].strip()
                    content_length = response.headers.get("content-length")
                    max_mb = max_bytes / 1024 / 1024
                    if content_length is not None and int(content_length) > max_bytes:
                        raise RemoteFetchError(
                            f"The remote file is larger than the {max_mb:.0f} MB limit."
                        )

                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise RemoteFetchError(
                                f"The remote file exceeds the {max_mb:.0f} MB limit."
                            )
                        chunks.append(chunk)

                    return FetchedResource(
                        content=b"".join(chunks),
                        content_type=content_type,
                        final_url=str(response.url),
                    )
            except httpx.TimeoutException as exc:
                raise RemoteFetchError("Timed out while fetching the URL.") from exc
            except httpx.TransportError as exc:
                raise RemoteFetchError(f"Could not reach the URL: {exc}") from exc

        raise RemoteFetchError(f"Too many redirects (limit {max_redirects}).")
