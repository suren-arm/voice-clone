"""Experimental Armenian support.

STATUS (verified 2026-09-11)
---------------------------
**No open-source zero-shot voice-cloning model natively supports Armenian.**
Chatterbox Multilingual's ``SUPPORTED_LANGUAGES`` is a 23-entry dict with no
``hy``; XTTS-v2 ships 17 languages without Armenian; CosyVoice 2 covers
zh/en/ja/ko plus Chinese dialects; F5-TTS's public checkpoints are zh/en.

Native Armenian TTS *without cloning* does exist (``facebook/mms-tts-hye`` /
``mms-tts-hyw``, CC-BY-NC-4.0), and eSpeak NG has verified Armenian voices
(``hy`` East Armenian, ``hyw`` West Armenian) usable for grapheme-to-phoneme.

What this module provides
-------------------------
A **clearly-labelled experimental** bridge: Armenian script is transliterated
into the orthography of a language the cloner *does* support, so the model's
own G2P produces an approximation of Armenian phonology in the user's cloned
voice.

Cyrillic (Russian) is the default target, not Latin, because Russian
orthography is far closer to Armenian phonology: ж/ш/ч/ц/х/дз map almost
one-to-one onto ժ/շ/չ/ց/խ/ձ, and Russian letter-to-sound is highly regular.
Latin/English is offered as a fallback for Western Armenian speakers who
prefer it.

This is an approximation, not Armenian TTS. Expect a noticeable foreign accent,
wrong stress placement (Armenian stresses the last syllable; Russian does not),
and occasional mispronunciation of consonant clusters.

**Nothing in the speech path calls this.** It used to: a cloned voice asked
for Armenian was transliterated through here so the model could approximate
it. That was removed, because espeak-ng's ``hy``/``hyw`` voices speak Armenian
natively and are offered instead -- an approximation that is strictly worse
than the supported path should not be reachable. This module stays as the
documented starting point for the fine-tuning work below, and as a way to
inspect what such a bridge actually produces.

The production path is documented in ``docs/ARMENIAN.md``: fine-tune Chatterbox
on Armenian speech with tokenizer vocabulary extension.
"""

from __future__ import annotations

import shutil
import subprocess
import unicodedata
from dataclasses import dataclass

#: Pseudo language code the API accepts for the experimental path.
ARMENIAN_CODE = "hy"
ARMENIAN_NAME = "Armenian (experimental)"

#: Eastern Armenian letter -> Russian Cyrillic approximation.
_HY_TO_RU: dict[str, str] = {
    "ա": "а",
    "բ": "б",
    "գ": "г",
    "դ": "д",
    "ե": "е",
    "զ": "з",
    "է": "э",
    "ը": "ы",
    "թ": "т",
    "ժ": "ж",
    "ի": "и",
    "լ": "л",
    "խ": "х",
    "ծ": "ц",
    "կ": "к",
    "հ": "һ",
    "ձ": "дз",
    "ղ": "г",
    "ճ": "ч",
    "մ": "м",
    "յ": "й",
    "ն": "н",
    "շ": "ш",
    "ո": "о",
    "չ": "ч",
    "պ": "п",
    "ջ": "дж",
    "ռ": "р",
    "ս": "с",
    "վ": "в",
    "տ": "т",
    "ր": "р",
    "ց": "ц",
    "ւ": "в",
    "փ": "п",
    "ք": "к",
    "օ": "о",
    "ֆ": "ф",
}

#: Eastern Armenian letter -> Latin approximation (read by an English/German G2P).
_HY_TO_LATIN: dict[str, str] = {
    "ա": "a",
    "բ": "b",
    "գ": "g",
    "դ": "d",
    "ե": "e",
    "զ": "z",
    "է": "e",
    "ը": "uh",
    "թ": "t",
    "ժ": "zh",
    "ի": "i",
    "լ": "l",
    "խ": "kh",
    "ծ": "ts",
    "կ": "k",
    "հ": "h",
    "ձ": "dz",
    "ղ": "gh",
    "ճ": "tch",
    "մ": "m",
    "յ": "y",
    "ն": "n",
    "շ": "sh",
    "ո": "o",
    "չ": "ch",
    "պ": "p",
    "ջ": "j",
    "ռ": "rr",
    "ս": "s",
    "վ": "v",
    "տ": "t",
    "ր": "r",
    "ց": "ts",
    "ւ": "v",
    "փ": "p",
    "ք": "k",
    "օ": "o",
    "ֆ": "f",
}

#: Digraphs and word-initial allophones, applied before the letter tables.
_DIGRAPHS_RU: tuple[tuple[str, str], ...] = (("ու", "у"), ("և", "ев"), ("եւ", "ев"))
_DIGRAPHS_LATIN: tuple[tuple[str, str], ...] = (("ու", "u"), ("և", "yev"), ("եւ", "yev"))

#: Armenian punctuation -> Latin punctuation the model's tokenizer understands.
_PUNCTUATION: tuple[tuple[str, str], ...] = (
    ("։", "."),  # ARMENIAN FULL STOP  ։
    ("՝", ","),  # ARMENIAN COMMA      ՝
    ("՜", "!"),  # ARMENIAN EXCLAMATION ՜
    ("՞", "?"),  # ARMENIAN QUESTION   ՞
    ("՚", "'"),  # APOSTROPHE          ՚
    ("՛", ""),  # EMPHASIS MARK       ՛
    ("֊", "-"),  # ARMENIAN HYPHEN     ֊
    ("․", "."),
)

_TARGETS = {"ru": (_HY_TO_RU, _DIGRAPHS_RU), "en": (_HY_TO_LATIN, _DIGRAPHS_LATIN)}


@dataclass(frozen=True)
class ArmenianTransliteration:
    """Result of bridging Armenian text into a supported language."""

    text: str
    target_language: str
    coverage: float
    """Fraction of Armenian letters that had a mapping (1.0 = fully mapped)."""


def contains_armenian(text: str) -> bool:
    """True if the string contains any character in the Armenian block."""
    return any("԰" <= ch <= "֏" for ch in text)


def transliterate(text: str, target_language: str = "ru") -> ArmenianTransliteration:
    """Transliterate Armenian script into ``target_language``'s orthography.

    ``target_language`` must be ``"ru"`` (recommended) or ``"en"``.
    Non-Armenian characters pass through untouched, so mixed-script input works.
    """
    if target_language not in _TARGETS:
        raise ValueError(
            f"Unsupported transliteration target '{target_language}'. "
            f"Choose one of: {', '.join(sorted(_TARGETS))}"
        )
    letters, digraphs = _TARGETS[target_language]

    normalized = unicodedata.normalize("NFC", text)
    for src, dst in _PUNCTUATION:
        normalized = normalized.replace(src, dst)

    # Word-initial ե / ո are pronounced /je/ and /vo/ in Eastern Armenian.
    initial = {"ru": {"ե": "е", "ո": "во"}, "en": {"ե": "ye", "ո": "vo"}}[target_language]

    out: list[str] = []
    total = mapped = 0
    i = 0
    at_word_start = True
    lowered = normalized.lower()

    while i < len(lowered):
        for src, dst in digraphs:
            if lowered.startswith(src, i):
                out.append(dst)
                total += len(src)
                mapped += len(src)
                i += len(src)
                at_word_start = False
                break
        else:
            ch = lowered[i]
            if "԰" <= ch <= "֏":
                total += 1
                if at_word_start and ch in initial:
                    out.append(initial[ch])
                    mapped += 1
                elif ch in letters:
                    out.append(letters[ch])
                    mapped += 1
                # Unmapped Armenian characters are dropped rather than emitted
                # raw: the target tokenizer would render them as noise.
                at_word_start = False
            else:
                out.append(ch)
                at_word_start = not ch.isalnum()
            i += 1

    coverage = (mapped / total) if total else 1.0
    return ArmenianTransliteration(
        text="".join(out).strip(),
        target_language=target_language,
        coverage=round(coverage, 4),
    )


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------


def espeak_available() -> bool:
    return shutil.which("espeak-ng") is not None


def armenian_ipa(text: str, *, dialect: str = "hy") -> str | None:
    """Return an IPA transcription of Armenian text using eSpeak NG.

    ``dialect`` is ``"hy"`` (East Armenian) or ``"hyw"`` (West Armenian); both
    are verified eSpeak NG voices. Returns ``None`` when eSpeak NG is absent.

    Not used for synthesis today -- Chatterbox consumes graphemes, not phonemes.
    It exists so the Armenian fine-tuning path in ``docs/ARMENIAN.md`` has a
    working G2P to build a phoneme-aligned dataset with, and so the quality of
    the transliteration above can be inspected.
    """
    if dialect not in {"hy", "hyw"}:
        raise ValueError("dialect must be 'hy' (East) or 'hyw' (West) Armenian")
    if not espeak_available():
        return None
    try:
        proc = subprocess.run(
            ["espeak-ng", "-v", dialect, "-q", "--ipa", text],
            capture_output=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").strip() or None
