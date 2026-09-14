"""Version 1 router aggregation.

Everything hangs off ``/api/v1``. Adding ``/api/v2`` later means mounting a
second router; existing web and mobile clients keep working against v1.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import ai_providers, books, speech, stories, system, voices

api_router = APIRouter()
api_router.include_router(voices.router)
api_router.include_router(speech.speech_router)
api_router.include_router(speech.generations_router)
api_router.include_router(stories.router)
api_router.include_router(books.router)
api_router.include_router(ai_providers.router)
api_router.include_router(system.router)
