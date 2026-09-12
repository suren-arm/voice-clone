"""Paragraph/sentence-safe chunking for long-form narration."""

from ai.text_chunking import chunk_text


def test_short_text_is_a_single_chunk():
    assert chunk_text("Hello there.", max_chars=900) == ["Hello there."]


def test_empty_text_yields_no_chunks():
    assert chunk_text("   ", max_chars=900) == []


def test_long_text_splits_at_sentence_boundaries_never_mid_word():
    text = "This is a sentence. " * 100
    chunks = chunk_text(text, max_chars=200)
    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)
    # Every chunk boundary lands after a terminator, never inside a word.
    for chunk in chunks:
        assert not chunk[-1].isalpha() or chunk == chunks[-1]
    rejoined = " ".join(chunks)
    assert "sentence." in rejoined


def test_paragraphs_are_kept_together_when_they_fit():
    text = "Para one.\n\nPara two.\n\nPara three."
    chunks = chunk_text(text, max_chars=100)
    assert chunks == [text]


def test_pathological_single_long_sentence_splits_at_word_boundaries():
    text = "word " * 500  # no terminal punctuation at all
    chunks = chunk_text(text.strip(), max_chars=100)
    assert all(len(chunk) <= 100 for chunk in chunks)
    # No word was cut in half: every chunk's pieces are whole "word" tokens.
    for chunk in chunks:
        assert all(token == "word" for token in chunk.split())


def test_armenian_sentence_terminator_is_respected():
    text = "Բարև։ " * 60
    chunks = chunk_text(text, max_chars=50)
    assert all(len(chunk) <= 50 for chunk in chunks)
    assert all("Բարև" in chunk for chunk in chunks)
