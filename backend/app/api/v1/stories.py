"""``/api/v1/stories`` -- AI fairy-tale generation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.api.deps import StoryServiceDep, limit_story
from app.schemas.common import ErrorResponse
from app.schemas.story import StoryRequest, StoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stories", tags=["stories"])

_ERRORS = {
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.post(
    "/generate",
    response_model=StoryResponse,
    responses=_ERRORS,
    summary="Generate a fairy tale from story parameters",
    dependencies=[Depends(limit_story)],
)
async def generate_story(payload: StoryRequest, stories: StoryServiceDep) -> StoryResponse:
    return await run_in_threadpool(stories.generate, payload)
