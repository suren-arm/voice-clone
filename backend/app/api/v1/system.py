"""``/api/v1/system`` -- capability discovery.

The frontend hardcodes no language list, no size limit and no format list: it
reads them from here at load time. Mobile clients will do the same, which is
what keeps the three clients from drifting apart as the engine changes.
"""

from __future__ import annotations

from fastapi import APIRouter

from ai.audio_processing import ALLOWED_EXTENSIONS, ffmpeg_available
from ai.model_loader import describe_device
from app import __version__
from app.api.deps import EngineDep, SettingsDep
from app.schemas.common import (
    EngineDescription,
    LimitsDescription,
    SystemInfo,
)
from app.services.language import language_options

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", response_model=SystemInfo, summary="Engine capabilities and limits")
def system_info(engine: EngineDep, settings: SettingsDep) -> SystemInfo:
    info = engine.info()
    return SystemInfo(
        app_name=settings.app_name,
        version=__version__,
        environment=settings.environment,
        engine=EngineDescription(
            name=info.name,
            variant=info.variant,
            device=info.device,
            sample_rate=info.sample_rate,
            loaded=engine.is_loaded,
            supports_streaming=info.supports_streaming,
            supports_cached_conditioning=info.supports_cached_conditioning,
            watermarked=info.watermarked,
            license=info.license,
            notes=info.notes or None,
        ),
        device_details=describe_device(info.device) | {"ffmpeg": ffmpeg_available()},
        languages=language_options(engine),
        limits=LimitsDescription(
            max_upload_bytes=settings.max_upload_bytes,
            min_reference_seconds=settings.min_reference_seconds,
            max_reference_seconds=settings.max_reference_seconds,
            max_text_chars=settings.max_text_chars,
            max_voices=settings.max_voices,
            require_consent=settings.require_consent,
            max_pdf_bytes=settings.max_pdf_bytes,
            max_pdf_pages=settings.max_pdf_pages,
            max_remote_download_bytes=settings.max_remote_download_bytes,
            max_book_narration_chars=settings.max_book_narration_chars,
        ),
        accepted_audio_formats=sorted(ext.lstrip(".") for ext in ALLOWED_EXTENSIONS),
    )
