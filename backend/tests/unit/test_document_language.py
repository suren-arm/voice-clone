"""Book Reader language detection -- English vs Armenian, nothing else."""

from __future__ import annotations

from app.services.documents.language import detect_language


def test_detects_english():
    assert detect_language("Once upon a time, in a quiet town, a fox and a rabbit met.") == "en"


def test_detects_armenian():
    assert detect_language("Մի անգամ մի փոքրիկ քաղաքում ապրում էր մի աղջիկ։") == "hy"


def test_mixed_but_mostly_armenian_defaults_to_armenian():
    text = "Chapter One. " + "Մի անգամ մի փոքրիկ քաղաքում ապրում էր մի աղջիկ։ " * 5
    assert detect_language(text) == "hy"


def test_empty_text_defaults_to_english():
    assert detect_language("") == "en"


def test_no_letters_defaults_to_english():
    assert detect_language("12345 !!! ---") == "en"
