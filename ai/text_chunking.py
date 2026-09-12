"""Paragraph/sentence-safe text chunking for long-form narration.

A single TTS call over an entire fairy tale is both risky (one failure loses
everything) and, for some engines, a quality regression on very long inputs.
This splits text into chunks that respect natural boundaries -- paragraphs
first, then sentences -- and never inside a word, so the audio concatenated
back together keeps its natural pauses.
"""

from __future__ import annotations

import re

#: Sentence terminators across the languages this app speaks: '.', '!', '?'
#: for English, '։' (Armenian full stop) and the same Latin punctuation for
#: Armenian text that borrows it.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?։])\s+")


def _split_sentences(paragraph: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT_RE.split(paragraph.strip()) if s]


def chunk_text(text: str, *, max_chars: int = 900) -> list[str]:
    """Split ``text`` into chunks no longer than ``max_chars``.

    Paragraphs (blank-line separated) are kept together when they fit. An
    over-long paragraph is split at sentence boundaries; an over-long single
    "sentence" (no terminal punctuation within reach) is split at word
    boundaries as a last resort -- never mid-word.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        flush()
        for sentence in _split_sentences(paragraph):
            if len(sentence) > max_chars:
                # Pathological: one "sentence" longer than a whole chunk.
                # Fall back to word-boundary splitting.
                words = sentence.split(" ")
                piece = ""
                for word in words:
                    trial = f"{piece} {word}".strip()
                    if len(trial) > max_chars and piece:
                        chunks.append(piece)
                        piece = word
                    else:
                        piece = trial
                if piece:
                    current = piece
                continue

            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
            else:
                flush()
                current = sentence
        flush()

    flush()
    return chunks
