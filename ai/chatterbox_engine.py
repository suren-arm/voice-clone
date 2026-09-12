"""Chatterbox (Resemble AI) implementation of :class:`VoiceCloningEngine`.

Verified against the actual installed package, ``chatterbox-tts==0.1.7`` (the
latest release on PyPI), 2026-09-12 -- by installing it and inspecting the
real class signatures directly, not by reading GitHub's ``main`` branch. The
two differ: ``main`` has since grown a Nano checkpoint and multilingual
checkpoint-version selection that this pinned release does not expose. Do not
"fix" the calls below to match ``main`` without first confirming a matching
PyPI release exists -- see the git history of this file for what that looked
like and why it crashed in production.

* ``ChatterboxMultilingualTTS.from_pretrained(device)`` -- no checkpoint
  selection; always loads the ``t3_mtl23ls_v2`` checkpoint.
* ``ChatterboxTTS.from_pretrained(device)`` (English) and
  ``ChatterboxTurboTTS.from_pretrained(device)`` (Turbo, 350M, English) --
  also no extra keyword arguments. There is no Nano checkpoint available
  through this class in this release; ``nano`` is consequently not offered as
  a variant here (offering it would mean a variant name whose reported size
  and behaviour don't match what actually loads).
* All three ``generate(text, ..., audio_prompt_path=..., exaggeration=...,
  cfg_weight=..., temperature=..., repetition_penalty=..., min_p=..., top_p=...)``;
  only the multilingual one also takes ``language_id``.
* ``model.sr`` is ``S3GEN_SR == 24000`` for all three.
* ``SUPPORTED_LANGUAGES`` is a 23-entry ``{code: name}`` dict (multilingual only).
* ``prepare_conditionals(wav_path, exaggeration=...)`` populates ``model.conds``,
  a ``Conditionals`` dataclass with ``.save(path)`` / ``.load(path)`` -- but
  **each of the three modules defines its own distinct ``Conditionals``
  class** (verified: none of the three are the same object), so loading a
  cache back requires importing the class from the same module the engine's
  own variant uses, not a single shared one.

That last point is what makes a *voice profile* cheap here: the expensive part
of cloning (speaker encoder + speech tokenizer + S3Gen reference embedding) is
computed once at voice-creation time and reloaded from disk on every
generation, instead of re-running on the reference clip each call.

Chatterbox also watermarks every output with Resemble's PerTh watermarker --
provenance we get for free rather than bolting on.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import numpy as np

from ai.engine import (
    EngineError,
    EngineInfo,
    SynthesisRequest,
    SynthesisResult,
    UnsupportedLanguageError,
    VoiceCloningEngine,
    VoiceProfile,
)
from ai.model_loader import resolve_device

logger = logging.getLogger(__name__)

CHATTERBOX_SAMPLE_RATE = 24_000
CONDITIONING_FILENAME = "conds.pt"

#: Mirrors ``chatterbox.mtl_tts.SUPPORTED_LANGUAGES`` (verified 2026-09-11).
#: Duplicated so that ``info()`` works without importing torch -- the API's
#: ``/system/info`` and the OpenAPI schema must not require a loaded model.
SUPPORTED_LANGUAGES: dict[str, str] = {
    "ar": "Arabic",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sv": "Swedish",
    "sw": "Swahili",
    "tr": "Turkish",
    "zh": "Chinese",
}

ENGLISH_ONLY_LANGUAGES = {"en": "English"}

#: "nano" is deliberately not offered: chatterbox-tts 0.1.7 has no Nano
#: checkpoint reachable through any public API, so a "nano" variant here
#: would silently load the 350M Turbo model while claiming a smaller one.
#: "turbo" is the CPU-appropriate choice this package actually provides.
_VARIANTS = {"multilingual", "english", "turbo"}


class ChatterboxEngine(VoiceCloningEngine):
    """Zero-shot multilingual voice cloning via Chatterbox."""

    name = "chatterbox"

    def __init__(
        self,
        *,
        variant: str = "multilingual",
        device: str = "auto",
        default_exaggeration: float = 0.5,
        default_cfg_weight: float = 0.5,
        default_temperature: float = 0.8,
    ) -> None:
        if variant not in _VARIANTS:
            raise ValueError(
                f"Unknown Chatterbox variant '{variant}'. Choose one of: "
                f"{', '.join(sorted(_VARIANTS))}"
            )
        self.variant = variant
        self.device = resolve_device(device)
        self.default_exaggeration = default_exaggeration
        self.default_cfg_weight = default_cfg_weight
        self.default_temperature = default_temperature

        self._model = None
        # Guards weight loading *and* inference. A single model instance holds
        # mutable conditioning state (`model.conds`), so concurrent generate()
        # calls would interleave voices. One GPU cannot usefully run two of
        # these at once anyway -- see docs/ARCHITECTURE.md for the worker-pool
        # design that replaces this lock when one GPU is no longer enough.
        self._lock = threading.RLock()

    # -- lifecycle ---------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:  # re-check under lock
                return
            started = time.perf_counter()
            logger.info("Loading Chatterbox variant=%s device=%s", self.variant, self.device)
            try:
                self._model = self._build_model()
            except Exception as exc:
                raise EngineError(f"Failed to load Chatterbox model: {exc}") from exc
            logger.info("Chatterbox loaded in %.1fs", time.perf_counter() - started)

    def _build_model(self):
        if self.variant == "multilingual":
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            return ChatterboxMultilingualTTS.from_pretrained(device=self.device)
        if self.variant == "english":
            from chatterbox.tts import ChatterboxTTS

            return ChatterboxTTS.from_pretrained(device=self.device)

        from chatterbox.tts_turbo import ChatterboxTurboTTS

        return ChatterboxTurboTTS.from_pretrained(device=self.device)

    def unload(self) -> None:
        with self._lock:
            self._model = None
            try:
                import gc

                import torch

                gc.collect()
                if self.device == "cuda":
                    torch.cuda.empty_cache()
            except ImportError:  # pragma: no cover
                pass

    # -- description -------------------------------------------------------

    def info(self) -> EngineInfo:
        multilingual = self.variant == "multilingual"
        sizes = {
            "multilingual": "0.5B",
            "english": "0.5B",
            "turbo": "350M",
        }
        return EngineInfo(
            name=self.name,
            variant=self.variant,
            device=self.device,
            sample_rate=CHATTERBOX_SAMPLE_RATE,
            languages=dict(SUPPORTED_LANGUAGES if multilingual else ENGLISH_ONLY_LANGUAGES),
            # Upstream exposes no incremental/chunked generate() API as of
            # 2026-09-11; generation is whole-utterance.
            supports_streaming=False,
            supports_cached_conditioning=True,
            watermarked=True,
            license="MIT (code and weights)",
            notes=(
                f"Chatterbox {self.variant} ({sizes[self.variant]}), 24 kHz output, "
                "PerTh watermark applied to every generation."
            ),
        )

    # -- voice profiles ----------------------------------------------------

    def create_voice(
        self,
        voice_id: str,
        audio_path: str | Path,
        *,
        workdir: str | Path,
    ) -> VoiceProfile:
        """Pre-compute and persist the speaker conditioning for ``audio_path``.

        The reference clip is kept too: conditioning is a derived cache tied to
        this model revision, and is silently recomputed if it fails to load.
        """
        audio_path = Path(audio_path)
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        self.load()

        conditioning_path = workdir / CONDITIONING_FILENAME
        started = time.perf_counter()
        with self._lock:
            try:
                self._model.prepare_conditionals(
                    str(audio_path), exaggeration=self.default_exaggeration
                )
                self._model.conds.save(conditioning_path)
            except Exception as exc:
                raise EngineError(f"Failed to derive voice conditioning: {exc}") from exc
        elapsed = time.perf_counter() - started
        logger.info("Conditioned voice %s in %.2fs", voice_id, elapsed)

        return VoiceProfile(
            voice_id=voice_id,
            reference_path=audio_path,
            conditioning_path=conditioning_path,
            engine=self.name,
            metadata={
                "variant": self.variant,
                "conditioning_seconds": round(elapsed, 3),
                # Chatterbox uses at most the first 6s (speech-token prompt) and
                # 10s (S3Gen reference) of the clip.
                "reference_window_seconds": 10,
            },
        )

    def _conditionals_class(self):
        """The ``Conditionals`` dataclass for this variant's module.

        Each of chatterbox's three model modules (``mtl_tts``, ``tts``,
        ``tts_turbo``) defines its own distinct ``Conditionals`` class --
        verified directly against the installed package, not assumed -- so a
        cache saved by one must be loaded back with the same one. Picking this
        from ``self.variant`` rather than inspecting ``self._model.conds`` at
        call time matters because that attribute is still ``None`` the first
        time this process loads an *existing* voice (nothing has called
        ``prepare_conditionals`` on this model instance yet), which is the
        common case right after a restart or on a freshly started worker.
        """
        if self.variant == "multilingual":
            from chatterbox.mtl_tts import Conditionals

            return Conditionals
        if self.variant == "english":
            from chatterbox.tts import Conditionals

            return Conditionals

        from chatterbox.tts_turbo import Conditionals

        return Conditionals

    def _apply_conditioning(self, profile: VoiceProfile) -> str | None:
        """Load cached conditioning; return a fallback reference path if not.

        Returns ``None`` when the cache was applied (so ``generate`` must not be
        given ``audio_prompt_path``), or the reference WAV path when the caller
        must re-condition from audio.
        """
        cache = profile.conditioning_path
        reusable = cache is not None and profile.engine == self.name and Path(cache).is_file()
        if reusable:
            try:
                conds_cls = self._conditionals_class()
                self._model.conds = conds_cls.load(cache, map_location=self.device).to(self.device)
                return None
            except Exception as exc:  # noqa: BLE001 - cache is disposable
                logger.warning(
                    "Could not reuse conditioning cache for %s (%s); "
                    "re-conditioning from reference audio",
                    profile.voice_id,
                    exc,
                )

        reference = Path(profile.reference_path)
        if not reference.is_file():
            raise EngineError(
                f"Reference audio for voice {profile.voice_id} is missing; "
                "the voice must be recreated."
            )
        return str(reference)

    # -- synthesis ---------------------------------------------------------

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        text = request.text.strip()
        if not text:
            raise EngineError("Cannot synthesize empty text.")

        language = self.validate_language(request.language)
        self.load()

        exaggeration = _coalesce(request.exaggeration, self.default_exaggeration)
        cfg_weight = _coalesce(request.cfg_weight, self.default_cfg_weight)
        temperature = _coalesce(request.temperature, self.default_temperature)

        started = time.perf_counter()
        with self._lock:
            if request.seed is not None:
                _seed_everything(request.seed)

            audio_prompt_path = self._apply_conditioning(request.profile)

            kwargs: dict[str, object] = {
                "exaggeration": exaggeration,
                "cfg_weight": cfg_weight,
                "temperature": temperature,
            }
            if audio_prompt_path is not None:
                kwargs["audio_prompt_path"] = audio_prompt_path
            if self.variant == "multilingual":
                kwargs["language_id"] = language

            try:
                wav = self._model.generate(text, **kwargs)
            except ValueError as exc:
                # Chatterbox raises ValueError for an unsupported language_id.
                raise UnsupportedLanguageError(str(exc)) from exc
            except Exception as exc:
                raise EngineError(f"Speech generation failed: {exc}") from exc

        generation_seconds = time.perf_counter() - started
        audio = _to_mono_float32(wav)
        duration = audio.size / CHATTERBOX_SAMPLE_RATE

        logger.info(
            "Generated %.2fs of audio in %.2fs (RTF %.2f) voice=%s lang=%s",
            duration,
            generation_seconds,
            generation_seconds / duration if duration else float("inf"),
            request.profile.voice_id,
            language,
        )

        return SynthesisResult(
            audio=audio,
            sample_rate=CHATTERBOX_SAMPLE_RATE,
            duration_seconds=duration,
            generation_seconds=generation_seconds,
            watermarked=True,
            engine=f"{self.name}:{self.variant}",
            language=language,
        )

    # Chatterbox needs no language for the English-only variants, but callers
    # still send one; accept "en" only there.
    def supports_language(self, language: str) -> bool:
        return language.lower() in self.info().languages


def _coalesce(value: float | None, default: float) -> float:
    return default if value is None else float(value)


def _to_mono_float32(wav) -> np.ndarray:
    """Chatterbox returns a torch tensor shaped (1, N). Normalise that."""
    array = wav.detach().cpu().numpy() if hasattr(wav, "detach") else np.asarray(wav)
    array = np.asarray(array, dtype=np.float32)
    if array.ndim > 1:
        array = (
            array.reshape(array.shape[0], -1).mean(axis=0)
            if array.shape[0] > 1
            else array.reshape(-1)
        )
    return np.ascontiguousarray(array)


def _seed_everything(seed: int) -> None:
    import random

    import torch

    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
