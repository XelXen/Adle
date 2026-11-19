"""Model provider status and credential hand-off.

The credential routes are *internal*: only the Electron main process calls
them, after decrypting the key from OS secure storage. They are excluded from
the renderer's operation allowlist (``x-adle-internal``).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from adle_core.application.services import Services, get_services

router = APIRouter(prefix="/provider", tags=["provider"])

INTERNAL = {"x-adle-internal": True}


class ProviderCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(min_length=8, max_length=512, pattern=r"^[\x21-\x7e]+$")


class ProviderStatus(BaseModel):
    provider_id: str
    display_name: str
    base_url: str
    model: str
    key_configured: bool


def _status(services: Services) -> ProviderStatus:
    return ProviderStatus(
        provider_id="aihubmix",
        display_name="AIHubMix",
        base_url="https://aihubmix.com/v1",
        model="coding-kimi-k3-free",
        key_configured=services.credentials.has_api_key,
    )


@router.get("", operation_id="provider.status", response_model=ProviderStatus)
def provider_status(services: Services = Depends(get_services)) -> ProviderStatus:
    return _status(services)


@router.put(
    "/credential",
    operation_id="provider.set_credential",
    status_code=204,
    openapi_extra=INTERNAL,
)
def set_credential(
    credential: ProviderCredential, services: Services = Depends(get_services)
) -> Response:
    services.credentials.set_api_key(credential.api_key)
    return Response(status_code=204)


@router.delete(
    "/credential",
    operation_id="provider.clear_credential",
    status_code=204,
    openapi_extra=INTERNAL,
)
def clear_credential(services: Services = Depends(get_services)) -> Response:
    services.credentials.clear_api_key()
    return Response(status_code=204)
