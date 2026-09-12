"""``/api/v1/ai`` -- AI text-provider capability discovery.

The frontend never guesses which providers are configured: it reads this on
load and builds the provider selector from the response, exactly the same
pattern ``/api/v1/system/info`` already uses for languages/limits. Never
returns a key or any other secret -- only id/name/kind/availability.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AiProviderRegistryDep
from app.schemas.ai_provider import AiProviderInfo, AiProvidersResponse
from app.services.ai_providers import ProviderUnavailableError
from app.services.ai_providers.registry import AUTO_ID

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get(
    "/providers",
    response_model=AiProvidersResponse,
    summary="List AI text-generation providers and their availability",
)
def list_providers(registry: AiProviderRegistryDep) -> AiProvidersResponse:
    providers = [
        AiProviderInfo(
            id=provider.id,
            name=provider.display_name,
            kind=provider.kind,
            available=provider.is_available(),
        )
        for provider in registry.list()
    ]
    try:
        auto_resolves_to = registry.resolve(AUTO_ID).id
    except ProviderUnavailableError:
        auto_resolves_to = None

    return AiProvidersResponse(providers=providers, auto_resolves_to=auto_resolves_to)
