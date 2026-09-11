#!/usr/bin/env python3
"""Pre-fetch model weights into the Hugging Face cache.

Weights are never committed to git (see ``.gitignore``) and never baked into the
Docker image -- the cache is a mounted volume instead, so rebuilding the image
does not re-download gigabytes.

    python scripts/download_model.py                    # multilingual (default)
    python scripts/download_model.py --variant turbo
    python scripts/download_model.py --all
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.model_loader import CHATTERBOX_REPOS, download_chatterbox, hf_cache_dir

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
logger = logging.getLogger("download_model")


def directory_size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024**2


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--variant",
        default="multilingual",
        choices=sorted(CHATTERBOX_REPOS),
        help="Which Chatterbox model to fetch (default: multilingual).",
    )
    parser.add_argument("--all", action="store_true", help="Fetch every variant.")
    args = parser.parse_args()

    variants = sorted(CHATTERBOX_REPOS) if args.all else [args.variant]
    logger.info("Hugging Face cache: %s", hf_cache_dir())

    failed = []
    for variant in variants:
        logger.info("--- %s (%s) ---", variant, CHATTERBOX_REPOS[variant])
        try:
            path = download_chatterbox(variant)
        except Exception as exc:  # noqa: BLE001 - report and continue to the next
            logger.error("Failed to download %s: %s", variant, exc)
            failed.append(variant)
            continue
        logger.info("Downloaded to %s (%.0f MB)", path, directory_size_mb(path))

    if failed:
        logger.error("Failed: %s", ", ".join(failed))
        return 1
    logger.info("Done. The API will now start without downloading anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
