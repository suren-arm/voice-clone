"""Experimental Armenian transliteration."""

import pytest

from ai.armenian import contains_armenian, transliterate


def test_detects_armenian_script():
    assert contains_armenian("Բարև")
    assert not contains_armenian("Hello there")
    assert contains_armenian("Hello Բարև")  # mixed


def test_cyrillic_bridge_is_phonetically_plausible():
    result = transliterate("Բարև Ձեզ", "ru")
    assert result.text == "барев дзез"
    assert result.coverage == 1.0
    assert result.target_language == "ru"


def test_latin_bridge():
    assert transliterate("Բարև Ձեզ", "en").text == "baryev dzez"


def test_word_initial_allophones():
    # ե is /je/ and ո is /vo/ word-initially in Eastern Armenian.
    assert transliterate("երեկ", "en").text.startswith("ye")
    assert transliterate("որ", "en").text.startswith("vo")


def test_digraphs():
    assert "у" in transliterate("ուր", "ru").text
    assert transliterate("և", "en").text == "yev"


def test_armenian_punctuation_is_converted():
    assert transliterate("Բարև։", "ru").text.endswith(".")
    assert "՞" not in transliterate("Ինչպե՞ս", "ru").text


def test_non_armenian_passes_through():
    assert transliterate("hello 123", "ru").text == "hello 123"


def test_unknown_target_rejected():
    with pytest.raises(ValueError, match="Unsupported transliteration target"):
        transliterate("Բարև", "de")
