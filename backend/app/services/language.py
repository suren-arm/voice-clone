"""Language catalogue, including the experimental Armenian bridge.

The engine's native language set is the source of truth. This module layers the
*application's* view on top: which codes the API accepts, which are native, and
how a non-native request is translated into something the engine can speak.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai.armenian import ARMENIAN_CODE, ARMENIAN_NAME, contains_armenian, transliterate
from ai.engine import VoiceCloningEngine
from app.schemas.common import LanguageOption

#: Language the Armenian bridge transliterates into. Russian orthography is a
#: closer phonological fit for Eastern Armenian than Latin -- see ai/armenian.py.
ARMENIAN_BRIDGE_TARGET = "ru"

ARMENIAN_NOTICE = (
    "Armenian is not natively supported by this model. The text was "
    "transliterated into Russian orthography so the cloned voice can approximate "
    "Armenian pronunciation. Expect a noticeable accent and imperfect stress."
)


@dataclass(frozen=True)
class ResolvedLanguage:
    """How a requested language maps onto what the engine will actually be asked."""

    requested: str
    engine_language: str
    text: str
    experimental: bool = False
    notice: str | None = None


def language_options(engine: VoiceCloningEngine, *, include_armenian: bool) -> list[LanguageOption]:
    """Everything the API will accept in a ``language`` field."""
    options = [
        LanguageOption(code=code, name=name, native=True, experimental=False)
        for code, name in sorted(engine.info().languages.items(), key=lambda kv: kv[1])
    ]
    if include_armenian and ARMENIAN_BRIDGE_TARGET in engine.info().languages:
        options.append(
            LanguageOption(
                code=ARMENIAN_CODE,
                name=ARMENIAN_NAME,
                native=False,
                experimental=True,
                note=ARMENIAN_NOTICE,
            )
        )
    return options


def is_supported(engine: VoiceCloningEngine, language: str, *, include_armenian: bool) -> bool:
    language = language.lower()
    if language in engine.info().languages:
        return True
    return (
        include_armenian
        and language == ARMENIAN_CODE
        and ARMENIAN_BRIDGE_TARGET in engine.info().languages
    )


def resolve(
    engine: VoiceCloningEngine, language: str, text: str, *, include_armenian: bool
) -> ResolvedLanguage:
    """Translate a request's ``(language, text)`` into engine inputs.

    Native languages pass through untouched. Armenian is transliterated and
    flagged, so the response and the stored row both record that this was an
    approximation rather than real Armenian synthesis.
    """
    language = language.lower()
    if language in engine.info().languages:
        # Armenian script sent under a native tag would be dropped by the
        # tokenizer; bridge it rather than emit silence.
        if include_armenian and contains_armenian(text):
            result = transliterate(text, ARMENIAN_BRIDGE_TARGET)
            if ARMENIAN_BRIDGE_TARGET in engine.info().languages:
                return ResolvedLanguage(
                    requested=language,
                    engine_language=ARMENIAN_BRIDGE_TARGET,
                    text=result.text,
                    experimental=True,
                    notice=ARMENIAN_NOTICE,
                )
        return ResolvedLanguage(requested=language, engine_language=language, text=text)

    if include_armenian and language == ARMENIAN_CODE:
        result = transliterate(text, ARMENIAN_BRIDGE_TARGET)
        if not result.text:
            raise ValueError("The Armenian text could not be transliterated.")
        return ResolvedLanguage(
            requested=ARMENIAN_CODE,
            engine_language=ARMENIAN_BRIDGE_TARGET,
            text=result.text,
            experimental=True,
            notice=ARMENIAN_NOTICE,
        )

    supported = ", ".join(sorted(engine.info().languages))
    raise ValueError(f"Language '{language}' is not supported. Supported codes: {supported}")
