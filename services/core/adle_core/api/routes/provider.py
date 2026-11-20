"""Model providers: which there are, which may be used, and the hand-off of keys.

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

from adle_core.api import schemas
from adle_core.application.services import Services, get_services
from adle_core.errors import NotFoundError
from adle_core.generation.provider import ProviderConfig
from adle_core.generation.routing import Plan

router = APIRouter(prefix="/provider", tags=["provider"])

INTERNAL = {"x-adle-internal": True}

#: A provider's name as Adle writes it: never free text.
PROVIDER_ID = r"^[a-z][a-z0-9_-]{0,31}$"


class ProviderCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(min_length=8, max_length=512, pattern=r"^[\x21-\x7e]+$")
    #: Whose key this is. Without one, the first provider there is.
    provider_id: str | None = Field(default=None, pattern=PROVIDER_ID)


class ProviderSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: One provider's name, or "auto": every provider the learner has given a key for.
    selection: str = Field(pattern=PROVIDER_ID)


class ProviderCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(pattern=PROVIDER_ID)


class ProviderModel(BaseModel):
    #: As the provider names it.
    id: str
    #: As a person would name it.
    name: str


class ProviderUsage(BaseModel):
    """Adle's own count of today's requests to one provider.

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


class ProviderChoice(BaseModel):
    """One provider there is."""

    provider_id: str
    display_name: str
    base_url: str
    #: In the order they are asked: the first, and the ones that stand in when it is away.
    models: list[ProviderModel]
    key_configured: bool
    #: The learner chose this provider and no other.
    selected: bool
    #: By the learner's choice, a request could go here now.
    in_use: bool
    #: It answers in seconds rather than minutes.
    quick: bool
    #: False when the limits Adle keeps to are its own caution and not the provider's.
    limits_published: bool
    usage: ProviderUsage


class ProviderRoute(BaseModel):
    """Where one kind of request would go at this moment, and how long it may take."""

    provider_ids: list[str]
    names: list[str]
    #: To put after "Sends to": the first provider, and any that would be asked after it.
    sentence: str
    #: Why the first is first, when there was something to decide. Otherwise empty.
    reason: str
    #: About how long the whole thing takes at the first provider. Said as "about".
    wait_seconds: int
    #: Whether that comes from answers that arrived on this computer.
    wait_measured: bool


class ProviderRoutes(BaseModel):
    """Where each kind of request would go. Read just before saying where one will go."""

    #: A question asked in the middle of a lesson.
    ask: ProviderRoute
    #: A list of suggested concepts.
    curriculum: ProviderRoute
    #: A lesson and its pictures.
    lesson: ProviderRoute


class ProviderStatus(BaseModel):
    """The learner's choice, every provider there is, and where requests would go."""

    #: The provider a lesson would go to first.
    provider_id: str
    display_name: str
    base_url: str
    model: str
    model_name: str
    #: Whether anything can be asked at all, by the learner's choice.
    key_configured: bool
    #: One provider's name, or "auto".
    selection: str
    providers: list[ProviderChoice]
    routes: ProviderRoutes


def _usage(services: Services, config: ProviderConfig) -> ProviderUsage:
    usage = services.gateway.usage(config.provider_id)
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


def _route(services: Services, work: str, found: Plan) -> ProviderRoute:
    wait = services.generation.expected_wait(work)
    return ProviderRoute(
        provider_ids=list(found.provider_ids),
        names=list(found.names),
        sentence=found.sentence,
        reason=found.reason,
        wait_seconds=wait.seconds,
        wait_measured=wait.measured,
    )


def _status(services: Services) -> ProviderStatus:
    gateway = services.gateway
    plans = {work: gateway.plan(work) for work in ("ask", "curriculum", "lesson")}
    config = gateway.config
    selection = gateway.selection
    # A provider is in use if a request could go to it: it is in some plan, with a key.
    planned = {name for found in plans.values() for name in found.provider_ids}
    return ProviderStatus(
        provider_id=config.provider_id,
        display_name=config.display_name,
        base_url=config.base_url,
        model=config.model,
        model_name=config.models[0].name,
        key_configured=gateway.has_key,
        selection=selection,
        providers=[
            ProviderChoice(
                provider_id=item.provider_id,
                display_name=item.display_name,
                base_url=item.base_url,
                models=[ProviderModel(id=model.id, name=model.name) for model in item.models],
                key_configured=gateway.has_key_for(item.provider_id),
                selected=selection == item.provider_id,
                in_use=item.provider_id in planned and gateway.has_key_for(item.provider_id),
                quick=item.quick,
                limits_published=item.limits_published,
                usage=_usage(services, item),
            )
            for item in gateway.providers
        ],
        routes=ProviderRoutes(
            ask=_route(services, "ask", plans["ask"]),
            curriculum=_route(services, "curriculum", plans["curriculum"]),
            lesson=_route(services, "lesson", plans["lesson"]),
        ),
    )


def _known(services: Services, provider_id: str | None) -> str:
    """The provider meant: the one named, if Adle knows it, or the first there is."""
    if provider_id is None:
        return services.credentials.default_provider_id
    if not services.gateway.knows(provider_id):
        raise NotFoundError("Adle does not know that AI provider.")
    return provider_id


@router.get("", operation_id="provider.status", response_model=ProviderStatus)
def provider_status(services: Services = Depends(get_services)) -> ProviderStatus:
    return _status(services)


@router.get("/usage", operation_id="provider.usage", response_model=ProviderUsage)
def provider_usage(
    provider_id: str | None = Query(default=None, pattern=PROVIDER_ID),
    services: Services = Depends(get_services),
) -> ProviderUsage:
    """Today's count at one provider: the one named, or the one a lesson would go to."""
    name = provider_id if provider_id is not None else services.gateway.config.provider_id
    if not services.gateway.knows(name):
        raise NotFoundError("Adle does not know that AI provider.")
    config = next(item for item in services.gateway.providers if item.provider_id == name)
    return _usage(services, config)


@router.post(
    "/check",
    operation_id="provider.check",
    response_model=schemas.Job,
    status_code=202,
)
def check_provider(body: ProviderCheck, services: Services = Depends(get_services)) -> schemas.Job:
    """Ask one provider for one word, to find out whether its key works.

    It counts as one request there. Nothing of the learner's is sent.
    """
    return schemas.Job.model_validate(services.generation.check_provider(body.provider_id))


@router.put(
    "/credential",
    operation_id="provider.set_credential",
    status_code=204,
    openapi_extra=INTERNAL,
)
def set_credential(
    credential: ProviderCredential, services: Services = Depends(get_services)
) -> Response:
    provider_id = _known(services, credential.provider_id)
    services.credentials.set_api_key(credential.api_key, provider_id)
    # Whatever the provider said about the key before this one is no longer about this one.
    services.gateway.forget_trouble(provider_id)
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
    """Record the learner's choice: one provider, or every one they have a key for.

    No key is touched. Refused while something is being written.
    """
    services.generation.select_provider(selection.selection)
    return Response(status_code=204)
