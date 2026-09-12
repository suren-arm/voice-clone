"""``GET /api/v1/ai/providers`` response shapes.

Never carries a key or any configuration value -- only id/name/kind/
availability, so the frontend can build a provider selector without ever
being told (or able to infer) what credentials are or are not set beyond
the plain boolean it already needs to grey out a choice.
"""

from __future__ import annotations

from app.schemas.common import ApiModel


class AiProviderInfo(ApiModel):
    id: str
    name: str
    kind: str  # "paid" | "free-tier" | "local"
    available: bool


class AiProvidersResponse(ApiModel):
    providers: list[AiProviderInfo]
    #: What "auto" currently resolves to, or null if nothing is configured.
    auto_resolves_to: str | None
