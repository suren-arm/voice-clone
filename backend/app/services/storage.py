"""Filesystem layout and access.

    storage/
      voices/<voice_id>/reference.wav     preprocessed reference clip
      voices/<voice_id>/conds.pt          engine conditioning cache (optional)
      voices/<voice_id>/metadata.json     human-readable mirror of the DB row
      generated/<generation_id>.wav       generated speech
      tmp/                                scratch, always cleaned up

Every public method takes an ID that has already been validated by
:func:`app.core.security.is_safe_id`, and every path is additionally re-checked
with :func:`resolve_within`. Nothing here is ever served as a static mount --
files are read back through an API endpoint so access control has somewhere to
live.

A ``StorageBackend`` protocol is not introduced yet: there is exactly one
implementation and the S3 migration is documented rather than pre-built.
The method surface below is what an S3 version would implement.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.security import is_safe_id, resolve_within

logger = logging.getLogger(__name__)

REFERENCE_FILENAME = "reference.wav"
METADATA_FILENAME = "metadata.json"


class StorageError(RuntimeError):
    pass


@dataclass
class LocalStorage:
    settings: Settings

    def __post_init__(self) -> None:
        self.settings.ensure_directories()

    # -- voices ------------------------------------------------------------
    def voice_dir(self, voice_id: str, *, create: bool = False) -> Path:
        if not is_safe_id(voice_id, "voice"):
            raise StorageError(f"Invalid voice id: {voice_id!r}")
        path = resolve_within(self.settings.voices_dir, voice_id)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def reference_path(self, voice_id: str) -> Path:
        return self.voice_dir(voice_id) / REFERENCE_FILENAME

    def write_voice_metadata(self, voice_id: str, metadata: dict[str, Any]) -> Path:
        """Mirror the DB row next to the audio.

        Makes the storage tree self-describing: if the SQLite file is lost, the
        voices are still identifiable and re-importable.
        """
        path = self.voice_dir(voice_id, create=True) / METADATA_FILENAME
        path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        return path

    def delete_voice(self, voice_id: str) -> bool:
        """Remove the whole voice directory: reference audio, cache, metadata."""
        path = self.voice_dir(voice_id)
        if not path.exists():
            return False
        shutil.rmtree(path, ignore_errors=False)
        logger.info("Deleted voice directory", extra={"voice_id": voice_id})
        return True

    # -- generations -------------------------------------------------------
    def generation_path(self, generation_id: str) -> Path:
        if not is_safe_id(generation_id, "gen"):
            raise StorageError(f"Invalid generation id: {generation_id!r}")
        return resolve_within(self.settings.generated_dir, f"{generation_id}.wav")

    def delete_generation(self, generation_id: str) -> bool:
        path = self.generation_path(generation_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def delete_generation_file(self, filename: str) -> bool:
        """Delete by stored filename (used for cascade cleanup)."""
        generation_id = Path(filename).stem
        if not is_safe_id(generation_id, "gen"):
            logger.warning("Refusing to delete unexpected filename %r", filename)
            return False
        return self.delete_generation(generation_id)

    # -- housekeeping ------------------------------------------------------
    def cleanup_tmp(self) -> int:
        """Remove leftover scratch files (crash recovery on startup)."""
        removed = 0
        for entry in self.settings.tmp_dir.glob("*"):
            try:
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink()
                removed += 1
            except OSError:  # pragma: no cover - best effort
                logger.warning("Could not remove temp entry %s", entry.name)
        return removed

    def usage_bytes(self) -> int:
        total = 0
        for root in (self.settings.voices_dir, self.settings.generated_dir):
            for path in root.rglob("*"):
                if path.is_file():
                    total += path.stat().st_size
        return total
