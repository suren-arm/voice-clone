"""The application's language catalogue and per-voice capability model.

One list, used by every feature. Text to Speech, Create Fairy Tale and the
Book Reader all offer exactly :data:`APP_LANGUAGES`, and every "can this
voice actually say this?" question is answered here rather than
re-derived per screen.

Why this module exists in this shape
------------------------------------
The catalogue used to be generated from the *cloning* engine's language set
alone. That was wrong in both directions:

* It over-promised. It listed all 23 Chatterbox multilingual languages as
  selectable even though nothing else in the product supported them.
* It under-promised, and this is what users actually hit. Production runs
  ``CHATTERBOX_VARIANT=turbo``, which is English-only, so the list collapsed
  to a single entry -- and Armenian was appended only ``if "ru" in
  engine.languages`` (the bridge target), which turbo also lacks. Armenian
  therefore vanished from Text to Speech entirely, *despite* espeak-ng
  shipping real ``hy``/``hyw`` voices that were bootstrapped and working.

The fix is to stop treating one engine as the source of truth. A language is
offered when *any* voice this app can reach speaks it, and each option
carries flags saying which kinds of voice those are, so the UI can filter
instead of letting a user pick a combination that fails afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai.armenian import ARMENIAN_CODE
from ai.engine import VoiceCloningEngine
from ai.espeak_engine import DEFAULT_VOICES
from app.schemas.common import LanguageOption


@dataclass(frozen=True)
class AppLanguage:
    """One language the product supports end to end."""

    code: str
    #: English name, for logs, prompts and API consumers.
    name: str
    #: How speakers of the language write its name -- what the UI shows.
    native_name: str


#: The languages this product supports, in the order the UI presents them.
#: Adding one here is not enough on its own: it needs a default voice that
#: genuinely speaks it (see ai/espeak_engine.DEFAULT_VOICES) and, for story
#: generation, an entry in services/story_prompt._LANGUAGE_NAMES.
APP_LANGUAGES: tuple[AppLanguage, ...] = (
    AppLanguage(code="en", name="English", native_name="English"),
    AppLanguage(code=ARMENIAN_CODE, name="Armenian", native_name="Հայերեն"),
    AppLanguage(code="ru", name="Russian", native_name="Русский"),
)

APP_LANGUAGE_CODES: frozenset[str] = frozenset(lang.code for lang in APP_LANGUAGES)

_BY_CODE: dict[str, AppLanguage] = {lang.code: lang for lang in APP_LANGUAGES}


def get_language(code: str) -> AppLanguage | None:
    return _BY_CODE.get(code.lower())


# -- capability ------------------------------------------------------------


def default_voice_languages() -> frozenset[str]:
    """App languages with at least one built-in (espeak-ng) voice."""
    return frozenset(
        spec.language for spec in DEFAULT_VOICES if spec.language in APP_LANGUAGE_CODES
    )


def cloned_voice_languages(engine: VoiceCloningEngine) -> frozenset[str]:
    """App languages the *cloning* engine can genuinely synthesize.

    Deliberately no Armenian bridge here. Transliterating Armenian into
    Russian orthography so an English-trained model can approximate it is a
    research path (see docs/ARMENIAN.md), not a capability to advertise --
    the product blocks that combination and points at the real Armenian
    default voices instead.
    """
    return frozenset(code for code in engine.info().languages if code in APP_LANGUAGE_CODES)


def supported_languages(engine: VoiceCloningEngine) -> frozenset[str]:
    """Every app language some reachable voice can speak."""
    return default_voice_languages() | cloned_voice_languages(engine)


def language_options(engine: VoiceCloningEngine) -> list[LanguageOption]:
    """The catalogue the API publishes, in :data:`APP_LANGUAGES` order."""
    cloned = cloned_voice_languages(engine)
    default = default_voice_languages()
    options: list[LanguageOption] = []
    for language in APP_LANGUAGES:
        supports_default = language.code in default
        supports_cloned = language.code in cloned
        if not (supports_default or supports_cloned):
            # No voice can say it; offering it would be a promise we cannot keep.
            continue
        options.append(
            LanguageOption(
                code=language.code,
                name=language.native_name,
                english_name=language.name,
                supports_default_voice=supports_default,
                supports_cloned_voice=supports_cloned,
            )
        )
    return options


def is_supported(engine: VoiceCloningEngine, language: str) -> bool:
    return language.lower() in supported_languages(engine)


def can_voice_speak(engine: VoiceCloningEngine, *, is_cloned: bool, language: str) -> bool:
    """Whether one kind of voice can speak ``language``."""
    language = language.lower()
    if is_cloned:
        return language in cloned_voice_languages(engine)
    return language in default_voice_languages()


#: Shown to a child, so it names the thing to do next rather than the model
#: that cannot do it. The technical reason stays in the logs.
def unsupported_voice_message(language: str) -> str:
    entry = get_language(language)
    name = entry.native_name if entry else language
    return f"This voice cannot speak {name}. Please choose another voice."
