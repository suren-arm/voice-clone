"""Engine selection.

One process holds one engine instance: model weights are large and loading is
slow, so the instance is a module-level singleton created on first use.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from ai.engine import VoiceCloningEngine

logger = logging.getLogger(__name__)

_engine: VoiceCloningEngine | None = None
_lock = threading.Lock()


def _make_chatterbox(**kwargs) -> VoiceCloningEngine:
    from ai.chatterbox_engine import ChatterboxEngine

    return ChatterboxEngine(**kwargs)


def _make_mock(**kwargs) -> VoiceCloningEngine:
    from ai.mock_engine import MockEngine

    return MockEngine(**{k: v for k, v in kwargs.items() if k == "latency_seconds"})


_FACTORIES: dict[str, Callable[..., VoiceCloningEngine]] = {
    "chatterbox": _make_chatterbox,
    "mock": _make_mock,
}


def available_engines() -> list[str]:
    return sorted(_FACTORIES)


def get_engine(name: str = "chatterbox", **kwargs) -> VoiceCloningEngine:
    """Return the process-wide engine, creating it on first call.

    Weights are *not* loaded here -- call ``engine.load()`` (or let the first
    request trigger it) so that process start-up stays fast.
    """
    global _engine
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        factory = _FACTORIES.get(name.lower())
        if factory is None:
            raise ValueError(
                f"Unknown engine '{name}'. Available: {', '.join(available_engines())}"
            )
        logger.info("Creating voice engine '%s'", name)
        _engine = factory(**kwargs)
        return _engine


def reset_engine() -> None:
    """Drop the singleton (tests, and hot-swapping engines in development)."""
    global _engine
    with _lock:
        if _engine is not None:
            try:
                _engine.unload()
            except Exception:
                logger.exception("Engine unload failed during reset")
        _engine = None
