"""Model providers: which there are, which is in use, and the hand-off of keys.

The credential and selection routes are *internal*: only the Electron main
process calls them. It decrypts a key from OS secure storage and hands it over
after each launch, and it passes on the learner's choice of provider, which it
also keeps. They are excluded from the renderer's operation allowlist
(``x-adle-internal``).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from adle_core.application.services import Services, get_services
from adle_core.errors import NotFoundError
from adle_core.generation.provider import ProviderConfig

router = APIRouter(prefix="/provider", tags=["provider"])

INTERNAL = {"x-adle-internal": True}

#: A provider's name as Adle writes it: never free text.
PROVIDER_ID = r"^[a-z][a-z0-9_-]{0,31}$"


class ProviderCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(min_length=8, max_length=512, pattern=r"^[\x21-\x7e]+$")
    #: Whose key this is. Without one, the provider in use.
    provider_id: str | None = Field(default=None, pattern=PROVIDER_ID)


class ProviderSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(pattern=PROVIDER_ID)


class ProviderModel(BaseModel):
    #: As the provider names it.
    id: str
    #: As a person would name it.
    name: str


class ProviderChoice(BaseModel):
    """One provider the learner can choose."""

    provider_id: str
    display_name: str
    base_url: str
    #: In the order they are asked: the first, and the ones that stand in when it is away.
    models: list[ProviderModel]
    key_configured: bool
    selected: bool
    #: False when the limits Adle keeps to are its own caution and not the provider's.
    limits_published: bool


class ProviderStatus(BaseModel):
    """The provider in use, and every provider there is to choose from."""

    provider_id: str
    display_name: str
    base_url: str
    model: str
    model_name: str
    key_configured: bool
    providers: list[ProviderChoice]


class ProviderUsage(BaseModel):
    """Adle's own count of today's requests to the provider in use.

    An estimate: the provider keeps the real one.
    """

    provider_id: str
    requests_today: int
    requests_per_day: int
    tokens_today: int
    tokens_per_day: int
    requests_last_minute: int
    requests_per_minute: int
    resets_at: datetime
    #: False when these limits are Adle's own caution and not ones the provider publishes.
    limits_published: bool


def _choice(services: Services, config: ProviderConfig) -> ProviderChoice:
    return ProviderChoice(
        provider_id=config.provider_id,
        display_name=config.display_name,
        base_url=config.base_url,
        models=[ProviderModel(id=model.id, name=model.name) for model in config.models],
        key_configured=services.credentials.has_key_for(config.provider_id),
        selected=config.provider_id == services.gateway.config.provider_id,
        limits_published=config.limits_published,
    )


def _status(services: Services) -> ProviderStatus:
    config = services.gateway.config
    return ProviderStatus(
        provider_id=config.provider_id,
        display_name=config.display_name,
        base_url=config.base_url,
        model=config.model,
        model_name=config.models[0].name,
        key_configured=services.credentials.has_key_for(config.provider_id),
        providers=[_choice(services, item) for item in services.gateway.providers],
    )


def _known(services: Services, provider_id: str | None) -> str:
    """The provider meant: the one named, if Adle knows it, or the one in use."""
    if provider_id is None:
        return services.gateway.config.provider_id
    if not services.gateway.knows(provider_id):
        raise NotFoundError("Adle does not know that AI provider.")
    return provider_id


@router.get("", operation_id="provider.status", response_model=ProviderStatus)
def provider_status(services: Services = Depends(get_services)) -> ProviderStatus:
    return _status(services)


@router.get("/usage", operation_id="provider.usage", response_model=ProviderUsage)
def provider_usage(services: Services = Depends(get_services)) -> ProviderUsage:
    config = services.gateway.config
    usage = services.gateway.usage()
    return ProviderUsage(
        provider_id=config.provider_id,
        requests_today=usage.requests_today,
        requests_per_day=usage.limits.requests_per_day,
        tokens_today=usage.tokens_today,
        tokens_per_day=usage.limits.tokens_per_day,
        requests_last_minute=usage.requests_last_minute,
        requests_per_minute=usage.limits.requests_per_minute,
        resets_at=usage.resets_at,
        limits_published=config.limits_published,
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
    services.credentials.set_api_key(credential.api_key, _known(services, credential.provider_id))
    return Response(status_code=204)


@router.delete(
    "/credential",
    operation_id="provider.clear_credential",
    status_code=204,
    openapi_extra=INTERNAL,
)
def clear_credential(
    provider_id: str | None = Query(default=None, pattern=PROVIDER_ID),
    services: Services = Depends(get_services),
) -> Response:
    services.credentials.clear_api_key(_known(services, provider_id))
    return Response(status_code=204)


@router.put(
    "/selection",
    operation_id="provider.select",
    status_code=204,
    openapi_extra=INTERNAL,
)
def select_provider(
    selection: ProviderSelection, services: Services = Depends(get_services)
) -> Response:
    """Use another provider from now on. Its key stays where it is; so do the others'."""
    services.generation.select_provider(selection.provider_id)
    return Response(status_code=204)
