"""FastAPI application entry point.

uvicorn app.main:app --reload          # from backend/
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from ai.registry import get_engine
from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimiter, client_key
from app.db.session import init_db, session_scope
from app.schemas.common import HealthResponse
from app.services.default_voices import ensure_default_voices
from app.services.documents import cleanup_stale_documents
from app.services.storage import LocalStorage

logger = logging.getLogger(__name__)

DESCRIPTION = """
Open-source voice cloning API.

Record or upload 10-30 seconds of speech, create a reusable voice profile, then
generate speech from text in that voice.

**Responsible use.** Creating a voice requires an explicit consent assertion.
Every generation carries a neural watermark when the engine supports one, and
deleting a voice removes its reference audio, its speaker conditioning and all
audio generated from it.
""".strip()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.is_production)
    settings.ensure_directories()
    init_db(settings)

    storage = LocalStorage(settings)
    removed = storage.cleanup_tmp()
    if removed:
        logger.info("Cleaned %d stale temp entries", removed)

    with session_scope() as bootstrap_session:
        ensure_default_voices(bootstrap_session, storage)

    with session_scope() as cleanup_session:
        cleanup_stale_documents(cleanup_session, settings)

    engine = get_engine(settings.voice_engine, **settings.engine_kwargs())
    logger.info(
        "%s v%s starting | engine=%s variant=%s device=%s",
        settings.app_name,
        __version__,
        engine.name,
        engine.info().variant,
        engine.info().device,
    )
    if settings.preload_model:
        logger.info("Preloading model weights ...")
        try:
            engine.load()
        except Exception:
            logger.exception("Model preload failed; will retry on first request")

    app.state.engine = engine
    app.state.storage = storage
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.is_production)

    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        # Explicit origins only. A wildcard here would let any page on the
        # internet drive a user's browser into this API.
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "Authorization"],
        expose_headers=["Content-Range", "Accept-Ranges", "Content-Disposition", "Retry-After"],
        max_age=600,
    )
    # WAV compresses well; JSON even better. Audio range responses are excluded
    # by the minimum size in practice only for tiny clips, which is fine.
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    _global_limiter = RateLimiter(
        capacity=settings.rate_limit_global_per_minute,
        window_seconds=60.0,
        name="requests",
    )

    @app.middleware("http")
    async def request_middleware(request: Request, call_next) -> Response:
        if settings.rate_limit_enabled and request.url.path.startswith(settings.api_v1_prefix):
            try:
                _global_limiter.check(client_key(request))
            except Exception as exc:  # RateLimitedError -> handled response
                from fastapi.responses import JSONResponse

                from app.core.errors import RateLimitedError

                if not isinstance(exc, RateLimitedError):
                    raise
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"error": {"code": exc.code, "message": exc.message}},
                    headers={"Retry-After": str(exc.retry_after)},
                )

        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        # Defensive headers: the API also serves audio files.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith(settings.api_v1_prefix):
            logger.info(
                "%s %s -> %d (%.1f ms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        return response

    @app.get("/health", response_model=HealthResponse, tags=["system"], summary="Liveness probe")
    def health() -> HealthResponse:
        engine = getattr(app.state, "engine", None)
        return HealthResponse(
            status="ok",
            engine_loaded=bool(engine and engine.is_loaded),
            version=__version__,
        )

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "api": settings.api_v1_prefix,
        }

    return app


app = create_app()
