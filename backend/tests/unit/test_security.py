"""Path-traversal and input-sanitisation guarantees."""

from pathlib import Path

import pytest

from app.core.security import (
    is_safe_id,
    new_id,
    resolve_within,
    sanitize_display_name,
    sanitize_filename,
)


def test_new_id_has_prefix_and_validates():
    voice_id = new_id("voice")
    assert voice_id.startswith("voice_")
    assert is_safe_id(voice_id, "voice")
    assert not is_safe_id(voice_id, "gen")


def test_new_id_is_not_sequential():
    ids = {new_id("gen") for _ in range(200)}
    assert len(ids) == 200


@pytest.mark.parametrize(
    "value",
    [
        "../etc/passwd",
        "voice_../../x",
        "voice_",
        "voice_SHORT",
        "voice_toolongtobevalid123",
        "voice_abc/def12345",
        "",
        "voice_abc123def45\x00",
    ],
)
def test_is_safe_id_rejects_hostile_input(value):
    assert not is_safe_id(value, "voice")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        (r"C:\Users\me\clip.mp3", "clip.mp3"),
        ("....//evil.wav", "evil.wav"),
        (".hidden", "hidden"),
        ("my recording (1).m4a", "my_recording_1_.m4a"),
        ("", "upload"),
        (None, "upload"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_truncates_but_keeps_extension():
    name = sanitize_filename("a" * 300 + ".wav")
    assert len(name) <= 100
    assert name.endswith(".wav")


def test_sanitize_display_name_collapses_whitespace_and_controls():
    assert sanitize_display_name("  My\x00  Voice \n ") == "My Voice"


def test_resolve_within_allows_children(tmp_path: Path):
    assert resolve_within(tmp_path, "a", "b") == (tmp_path / "a" / "b").resolve()


@pytest.mark.parametrize("parts", [("..",), ("..", "..", "etc"), ("a", "..", "..", "x")])
def test_resolve_within_blocks_escape(tmp_path: Path, parts):
    with pytest.raises(ValueError, match="escapes"):
        resolve_within(tmp_path, *parts)
