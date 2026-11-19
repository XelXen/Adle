"""Model provider status and credential hand-off.

The credential routes are *internal*: only the Electron main process calls
them, after decrypting the key from OS secure storage. They are excluded from
the renderer's operation allowlist (``x-adle-internal``).
"""

from __future__ import annotations

from datetime import datetime

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


class ProviderUsage(BaseModel):
    """Adle's own count of today's requests. An estimate: the provider keeps the real one."""

    requests_today: int
    requests_per_day: int
    tokens_today: int
    tokens_per_day: int
    requests_last_minute: int
    requests_per_minute: int
    resets_at: datetime


def _status(services: Services) -> ProviderStatus:
    config = services.gateway.config
    return ProviderStatus(
        provider_id=config.provider_id,
        display_name=config.display_name,
        base_url=config.base_url,
        model=config.model,
        key_configured=services.credentials.has_api_key,
    )


@router.get("", operation_id="provider.status", response_model=ProviderStatus)
def provider_status(services: Services = Depends(get_services)) -> ProviderStatus:
    return _status(services)


@router.get("/usage", operation_id="provider.usage", response_model=ProviderUsage)
def provider_usage(services: Services = Depends(get_services)) -> ProviderUsage:
    usage = services.gateway.usage()
    return ProviderUsage(
        requests_today=usage.requests_today,
        requests_per_day=usage.limits.requests_per_day,
        tokens_today=usage.tokens_today,
        tokens_per_day=usage.limits.tokens_per_day,
        requests_last_minute=usage.requests_last_minute,
        requests_per_minute=usage.limits.requests_per_minute,
        resets_at=usage.resets_at,
    )


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
