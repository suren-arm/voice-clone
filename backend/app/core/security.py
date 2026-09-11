"""Input-hardening helpers used before anything touches the filesystem."""

from __future__ import annotations

import re
import secrets
import unicodedata
from pathlib import Path

_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
_SAFE_ID = re.compile(r"^[a-z]+_[a-z0-9]{12}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def new_id(prefix: str) -> str:
    """Opaque, non-sequential identifier, e.g. ``voice_k3f9a1b2c4d5``.

    Non-sequential on purpose: IDs appear in audio URLs, and sequential IDs
    would let anyone enumerate other users' generations.
    """
    suffix = "".join(secrets.choice(_ID_ALPHABET) for _ in range(12))
    return f"{prefix}_{suffix}"


def is_safe_id(value: str, prefix: str | None = None) -> bool:
    """Validate an ID *before* it is used to build a path.

    This is the primary defence against path traversal: IDs come from the
    client, and every storage path is ``<root>/<id>/...``.
    """
    if not isinstance(value, str) or not _SAFE_ID.match(value):
        return False
    return prefix is None or value.startswith(f"{prefix}_")


def sanitize_filename(name: str | None, *, fallback: str = "upload", max_length: int = 100) -> str:
    """Reduce a client-supplied filename to something safe to log and store.

    Strips directory components (including Windows ``\\`` separators), control
    characters and leading dots, then whitelists the remainder.
    """
    if not name:
        return fallback
    name = unicodedata.normalize("NFKC", name)
    name = _CONTROL_CHARS.sub("", name)
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).lstrip(".")
    name = re.sub(r"_{2,}", "_", name).strip("_")
    if not name or name in {".", ".."}:
        return fallback
    if len(name) > max_length:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 8:
            name = stem[: max_length - len(ext) - 1] + "." + ext
        else:
            name = name[:max_length]
    return name


def sanitize_display_name(value: str, *, max_length: int = 80) -> str:
    """Collapse whitespace and strip control characters from a user-visible name."""
    cleaned = _CONTROL_CHARS.sub("", unicodedata.normalize("NFC", value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length]


def resolve_within(root: Path, *parts: str) -> Path:
    """Join ``parts`` onto ``root`` and refuse to escape it.

    Belt-and-braces alongside :func:`is_safe_id`: even if a caller forgets to
    validate an ID, the resulting path cannot leave the storage root.
    """
    root = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Resolved path escapes the storage root")
    return candidate
