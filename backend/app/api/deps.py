"""FastAPI dependencies: settings, DB session, engine, services, rate limits."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from ai.engine import VoiceCloningEngine
from ai.registry import get_engine as get_engine_singleton
from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiter, client_key
from app.db.session import get_session_factory
from app.repositories.document_repo import DocumentSectionRepository
from app.services.ai_providers import AiProviderRegistry, build_default_registry
from app.services.documents import DocumentService, ReadingService
from app.services.speech_service import SpeechService
from app.services.storage import LocalStorage
from app.services.story_service import StoryService
from app.services.voice_service import VoiceService


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


def db_session(settings: SettingsDep) -> Iterator[Session]:
    """One transaction per request: commit on success, roll back on any error."""
    session = get_session_factory(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(db_session)]


def engine_dep(settings: SettingsDep) -> VoiceCloningEngine:
    return get_engine_singleton(settings.voice_engine, **settings.engine_kwargs())


EngineDep = Annotated[VoiceCloningEngine, Depends(engine_dep)]


def storage_dep(settings: SettingsDep) -> LocalStorage:
    return LocalStorage(settings)


StorageDep = Annotated[LocalStorage, Depends(storage_dep)]


def voice_service(
    session: SessionDep, settings: SettingsDep, engine: EngineDep, storage: StorageDep
) -> VoiceService:
    return VoiceService(session=session, settings=settings, engine=engine, storage=storage)


def speech_service(
    session: SessionDep, settings: SettingsDep, engine: EngineDep, storage: StorageDep
) -> SpeechService:
    return SpeechService(session=session, settings=settings, engine=engine, storage=storage)


def ai_provider_registry(settings: SettingsDep) -> AiProviderRegistry:
    return build_default_registry(settings)


AiProviderRegistryDep = Annotated[AiProviderRegistry, Depends(ai_provider_registry)]


def story_service(registry: AiProviderRegistryDep) -> StoryService:
    return StoryService(registry=registry)


def document_service(session: SessionDep, settings: SettingsDep) -> DocumentService:
    return DocumentService(session=session, settings=settings)


DocumentServiceDep = Annotated[DocumentService, Depends(document_service)]


def reading_service(session: SessionDep) -> ReadingService:
    return ReadingService(DocumentSectionRepository(session))


ReadingServiceDep = Annotated[ReadingService, Depends(reading_service)]


VoiceServiceDep = Annotated[VoiceService, Depends(voice_service)]
SpeechServiceDep = Annotated[SpeechService, Depends(speech_service)]
StoryServiceDep = Annotated[StoryService, Depends(story_service)]


# -- pagination -------------------------------------------------------------
class Pagination:
    def __init__(
        self,
        limit: int = Query(50, ge=1, le=200, description="Maximum items to return."),
        offset: int = Query(0, ge=0, description="Items to skip."),
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]


# -- rate limiters ----------------------------------------------------------
# Instantiated lazily so that settings changes in tests take effect.
_limiters: dict[str, RateLimiter] = {}


def _limiter(name: str, capacity: int, window: float) -> RateLimiter:
    limiter = _limiters.get(name)
    if limiter is None or limiter.capacity != capacity or limiter.window_seconds != window:
        limiter = RateLimiter(capacity=capacity, window_seconds=window, name=name)
        _limiters[name] = limiter
    return limiter


def reset_rate_limiters() -> None:
    for limiter in _limiters.values():
        limiter.reset()
    _limiters.clear()


def limit_voice_creation(request: Request, settings: SettingsDep) -> None:
    if not settings.rate_limit_enabled:
        return
    _limiter("voice creations", settings.rate_limit_voice_create_per_hour, 3600.0).check(
        client_key(request)
    )


def limit_speech(request: Request, settings: SettingsDep) -> None:
    if not settings.rate_limit_enabled:
        return
    _limiter("speech requests", settings.rate_limit_speech_per_hour, 3600.0).check(
        client_key(request)
    )


def limit_story(request: Request, settings: SettingsDep) -> None:
    if not settings.rate_limit_enabled:
        return
    _limiter("story requests", settings.rate_limit_story_per_hour, 3600.0).check(
        client_key(request)
    )


def limit_book_ingest(request: Request, settings: SettingsDep) -> None:
    """Guards PDF upload and URL fetch -- the latter makes an outbound request
    on the server's behalf, so it deserves its own, tighter budget."""
    if not settings.rate_limit_enabled:
        return
    _limiter("book ingest requests", settings.rate_limit_book_ingest_per_hour, 3600.0).check(
        client_key(request)
    )


def limit_book_narrate(request: Request, settings: SettingsDep) -> None:
    if not settings.rate_limit_enabled:
        return
    _limiter("book narration requests", settings.rate_limit_book_narrate_per_hour, 3600.0).check(
        client_key(request)
    )
