"""Best-effort document language detection: English or Armenian, nothing else.

This app's TTS layer only genuinely speaks two languages (see
``app/services/language.py``), so a general-purpose language-ID library would
be overkill -- and risk confidently naming a language this app cannot narrate
anyway. A simple Unicode-block ratio is enough to tell "this book is written
in Armenian" from "this book is written in English", and it never has to
guess at anything more exotic than that, matching how the rest of the app
already treats Armenian as a first-class special case (see ``ai/armenian.py``).

The detected language is only ever a *default*: the reading-range/narration
step always lets the caller override it (see ``reading_service.py``), so a
wrong guess here never sends Armenian text to an English-only voice with no
way out.
"""

from __future__ import annotations

_ARMENIAN_RANGE = ("԰", "֏")

#: If at least this fraction of the letters sampled are Armenian, the
#: document is called Armenian; otherwise it defaults to English. Deliberately
#: low: even a partial-Armenian document (mixed-language) should be flagged
#: as Armenian by default, since narrating it as English would mangle it,
#: while narrating genuinely-English text as Armenian is a much smaller
#: practical problem (the override control exists for exactly this).
_ARMENIAN_THRESHOLD = 0.15
#: Cap the amount of text scanned -- language does not need the whole book,
#: and this keeps detection O(1) in document size.
_SAMPLE_CHARS = 5000


def detect_language(text: str) -> str:
    """Return ``"hy"`` or ``"en"`` -- the only two languages this app narrates."""
    sample = text[:_SAMPLE_CHARS]
    letters = [ch for ch in sample if ch.isalpha()]
    if not letters:
        return "en"
    armenian_letters = sum(1 for ch in letters if _ARMENIAN_RANGE[0] <= ch <= _ARMENIAN_RANGE[1])
    return "hy" if armenian_letters / len(letters) >= _ARMENIAN_THRESHOLD else "en"
