"""Typed application settings, loaded from the environment / ``.env``."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- app ---------------------------------------------------------------
    app_name: str = "AI Voice Studio"
    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # -- server ------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000

    # -- cors --------------------------------------------------------------
    # NoDecode: pydantic-settings otherwise tries to JSON-decode any env var
    # mapped to a list field before this class's own comma-split validator
    # ever runs, so a plain "https://a.com,https://b.com" value (exactly
    # what every deployment doc here tells you to set) fails with
    # "error parsing value for field ... from source EnvSettingsSource"
    # before the validator gets a chance to handle it.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # -- storage -----------------------------------------------------------
    storage_dir: Path = Path("storage")
    database_url: str = "sqlite:///storage/voice_studio.db"

    # -- engine ------------------------------------------------------------
    voice_engine: str = "chatterbox"
    # "nano" is not offered: chatterbox-tts 0.1.7 (the pinned PyPI release)
    # has no Nano checkpoint reachable through any public API -- see
    # ai/chatterbox_engine.py's module docstring. "turbo" (350M) is the
    # CPU-appropriate choice this package actually provides.
    chatterbox_variant: Literal["multilingual", "english", "turbo"] = "multilingual"
    device: str = "auto"
    preload_model: bool = False

    default_exaggeration: float = 0.5
    default_cfg_weight: float = 0.5
    default_temperature: float = 0.8

    # -- limits ------------------------------------------------------------
    max_upload_bytes: int = 25 * 1024 * 1024
    min_reference_seconds: float = 3.0
    max_reference_seconds: float = 120.0
    max_text_chars: int = 2000
    max_voices: int = 100
    generation_timeout_seconds: int = 300
    require_consent: bool = True

    # -- rate limiting -----------------------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_voice_create_per_hour: int = 20
    rate_limit_speech_per_hour: int = 120
    rate_limit_global_per_minute: int = 240

    # -- experimental ------------------------------------------------------
    enable_experimental_armenian: bool = True

    # -- fairy-tale generation: multi-provider AI text generation ----------
    # None of these is mandatory -- StoryService works with any subset
    # configured, via AiProviderRegistry (app/services/ai_providers/). Model
    # defaults verified against each vendor's own current documentation/SDK
    # at implementation time (12 September 2026); re-verify periodically,
    # this space moves fast -- see README.md's "AI Providers" section.
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.5"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"
    # Self-hosted only -- see ai_providers/ollama_provider.py for why this
    # cannot run inside the same container as Chatterbox on the deployed
    # Render Starter instance.
    ollama_base_url: str | None = None
    ollama_model: str = "qwen2.5:7b"

    # "auto" mode: try this provider first if it's configured, before
    # falling through the built-in priority order. Unset = use the built-in
    # order (openai, gemini, anthropic, ollama).
    ai_preferred_provider: str | None = None
    # "auto" mode: try free-tier/local providers before paid ones, so a
    # deployment that has both a paid and a free provider configured
    # doesn't default to spending money on every request.
    ai_auto_prefer_free: bool = False

    rate_limit_story_per_hour: int = 30

    # -- book reader: document ingestion (PDF upload / HTTP(S) link) -------
    # Deliberately separate from max_upload_bytes (reference audio): PDFs and
    # audio have unrelated realistic size ranges, and letting one setting
    # bound both would either starve legitimate books or accept oversized
    # audio uploads.
    max_pdf_bytes: int = 20 * 1024 * 1024
    max_pdf_pages: int = 500
    # Same cap applies to a PDF fetched from a URL; a remote *HTML* page has
    # no separate cap of its own -- it is capped by the same constant, since
    # a normal article/book page is far smaller than this ceiling in practice.
    max_remote_download_bytes: int = 20 * 1024 * 1024
    book_fetch_connect_timeout_seconds: float = 5.0
    book_fetch_read_timeout_seconds: float = 20.0
    book_fetch_max_redirects: int = 5
    # How much text one "Start Reading" call may synthesize. Separate from
    # (and larger than) speech.ABSOLUTE_MAX_TEXT_CHARS, which bounds a single
    # hand-typed/generated-story request -- a book's selected page range is
    # expected to be longer, but must still fit inside Render's request
    # timeout on a CPU instance, so this is a deliberately bounded "batch",
    # not the whole book. See README.md's Book Reader section.
    max_book_narration_chars: int = 12_000
    # Extracted documents (metadata + section text, never the original PDF
    # bytes -- see services/documents/document_service.py) older than this
    # are swept on startup, mirroring LocalStorage.cleanup_tmp(). Books are
    # not meant to be a permanent library; re-upload or re-fetch is cheap.
    document_retention_hours: int = 24
    rate_limit_book_ingest_per_hour: int = 20
    rate_limit_book_narrate_per_hour: int = 30

    # -- validators --------------------------------------------------------
    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("storage_dir", mode="after")
    @classmethod
    def _absolute_storage(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    # -- derived -----------------------------------------------------------
    @property
    def voices_dir(self) -> Path:
        return self.storage_dir / "voices"

    @property
    def generated_dir(self) -> Path:
        return self.storage_dir / "generated"

    @property
    def tmp_dir(self) -> Path:
        return self.storage_dir / "tmp"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def resolved_database_url(self) -> str:
        """Make a relative SQLite path absolute w.r.t. the repository root."""
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return self.database_url
        raw = self.database_url[len(prefix) :]
        path = Path(raw)
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"{prefix}{path}"

    def ensure_directories(self) -> None:
        for directory in (self.storage_dir, self.voices_dir, self.generated_dir, self.tmp_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def engine_kwargs(self) -> dict[str, object]:
        """Constructor arguments for the configured engine."""
        if self.voice_engine == "chatterbox":
            return {
                "variant": self.chatterbox_variant,
                "device": self.device,
                "default_exaggeration": self.default_exaggeration,
                "default_cfg_weight": self.default_cfg_weight,
                "default_temperature": self.default_temperature,
            }
        return {}


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
