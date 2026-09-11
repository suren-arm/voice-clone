"""Model-agnostic voice cloning layer.

The rest of the application only ever talks to :class:`ai.engine.VoiceCloningEngine`.
Swapping Chatterbox for F5-TTS, CosyVoice 2 or XTTS-v2 means adding one module
here and changing ``VOICE_ENGINE`` in the environment -- no API or frontend change.
"""

from ai.engine import (
    EngineInfo,
    SynthesisRequest,
    SynthesisResult,
    VoiceCloningEngine,
    VoiceProfile,
)
from ai.registry import available_engines, get_engine, reset_engine

__all__ = [
    "EngineInfo",
    "SynthesisRequest",
    "SynthesisResult",
    "VoiceCloningEngine",
    "VoiceProfile",
    "available_engines",
    "get_engine",
    "reset_engine",
]
