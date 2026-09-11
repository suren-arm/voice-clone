"""Device selection and weight loading helpers.

Kept separate from the engine so that device policy, dtype policy and the
Hugging Face download path can be tested and reused without importing a model.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

#: Hugging Face repositories holding Chatterbox weights (verified 2026-09-11).
CHATTERBOX_REPOS: dict[str, str] = {
    "multilingual": "ResembleAI/chatterbox",
    "english": "ResembleAI/chatterbox",
    "turbo": "ResembleAI/chatterbox-turbo",
    "nano": "ResembleAI/chatterbox-nano",
}


def resolve_device(preference: str = "auto") -> str:
    """Pick a torch device.

    ``auto`` prefers CUDA, then Apple MPS, then CPU. An explicit preference is
    honoured unless the backend is unavailable, in which case we fall back and
    log loudly rather than crashing at request time.
    """
    preference = (preference or "auto").lower()
    try:
        import torch
    except ImportError:  # pragma: no cover - torch is a hard dependency in prod
        logger.warning("torch not installed; reporting device='cpu'")
        return "cpu"

    cuda = torch.cuda.is_available()
    mps = bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available()

    if preference == "auto":
        if cuda:
            return "cuda"
        if mps:
            return "mps"
        return "cpu"

    if preference == "cuda" and not cuda:
        logger.warning("DEVICE=cuda requested but CUDA is unavailable; using CPU")
        return "cpu"
    if preference == "mps" and not mps:
        logger.warning("DEVICE=mps requested but MPS is unavailable; using CPU")
        return "cpu"
    return preference


def describe_device(device: str) -> dict[str, object]:
    """Human-readable device details for ``GET /system/info``."""
    details: dict[str, object] = {"device": device}
    try:
        import torch
    except ImportError:  # pragma: no cover
        return details

    details["torch_version"] = torch.__version__
    if device == "cuda" and torch.cuda.is_available():
        idx = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(idx)
        details["gpu_name"] = props.name
        details["vram_total_mb"] = round(props.total_memory / 1024**2)
        details["vram_allocated_mb"] = round(torch.cuda.memory_allocated(idx) / 1024**2)
        details["cuda_version"] = torch.version.cuda
    return details


def hf_cache_dir() -> Path:
    """Resolve the Hugging Face cache directory actually in use."""
    for var in ("HF_HOME", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE"):
        value = os.environ.get(var)
        if value:
            base = Path(value)
            return base / "hub" if var == "HF_HOME" else base
    return Path.home() / ".cache" / "huggingface" / "hub"


def download_chatterbox(variant: str = "multilingual", *, quiet: bool = False) -> Path:
    """Pre-fetch Chatterbox weights into the HF cache.

    Used by ``scripts/download_model.py`` so that container start-up and the
    first API request do not pay a multi-GB download.
    """
    from huggingface_hub import snapshot_download

    repo_id = CHATTERBOX_REPOS.get(variant)
    if repo_id is None:
        raise ValueError(
            f"Unknown Chatterbox variant '{variant}'. "
            f"Choose one of: {', '.join(sorted(CHATTERBOX_REPOS))}"
        )
    if not quiet:
        logger.info("Downloading %s weights from %s ...", variant, repo_id)
    path = snapshot_download(repo_id=repo_id)
    return Path(path)
