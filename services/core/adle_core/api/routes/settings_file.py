"""The core's part of a settings file (ADR-064).

Every route here is *internal*: only the desktop shell calls it. The shell puts a settings
file together and takes one apart, because the look of the app, the choice of provider and
the keys are its to keep. These routes are for the part the core keeps: the learner's
preferences, and the voice. None of them takes a path, and none ever sees a key.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints

from adle_core.api import schemas
from adle_core.api.routes.voice import sources_of
from adle_core.application.services import Services, get_services

router = APIRouter(tags=["settings"])

INTERNAL = {"x-adle-internal": True}
ServicesDep = Annotated[Services, Depends(get_services)]

#: A part of a settings file as it was written: a few named values. What each may be is
#: decided where it is applied, one setting at a time.
_Name = Annotated[str, StringConstraints(max_length=60)]
SettingsPart = Annotated[dict[_Name, Any], Field(max_length=24)]


class CoreSettings(BaseModel):
    """What the core keeps of the learner's settings, as a file holds it."""

    learning: dict[str, Any]
    voice: dict[str, Any]


class SettingsToLookAt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice: SettingsPart | None = None


class VoicePlan(BaseModel):
    """What bringing a file's voice in would do on this computer."""

    #: The voice lessons would be read in; none for the computer's own.
    tier: Literal["kokoro", "expressive"] | None
    name: str | None
    #: It is not on this computer yet: setting it up downloads it.
    set_up: bool
    #: About how much is downloaded to set it up, and from where.
    download_bytes: int
    sources: list[str]
    #: Why it is not the voice the file names, when it is not.
    note: str


class SettingsLookedAt(BaseModel):
    voice: VoicePlan | None


class SettingsToBringIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning: SettingsPart | None = None
    voice: SettingsPart | None = None
    #: The learner said to set up a voice that is not on this computer (ADR-042).
    set_up_voice: StrictBool = False


class SettingsBroughtIn(BaseModel):
    #: What could not be had as the file has it, and what was done instead.
    notes: list[str]
    #: A voice being set up because of it.
    setting_up: schemas.Job | None


@router.get(
    "/settings-file",
    operation_id="settings.save_file",
    response_model=CoreSettings,
    openapi_extra=INTERNAL,
)
def settings_for_a_file(services: ServicesDep) -> CoreSettings:
    return CoreSettings.model_validate(services.settings_file.save())


@router.post(
    "/settings-file/look",
    operation_id="settings.look_at_file",
    response_model=SettingsLookedAt,
    openapi_extra=INTERNAL,
)
def look_at_settings(body: SettingsToLookAt, services: ServicesDep) -> SettingsLookedAt:
    """What a file's voice would be on this computer. Nothing is changed."""
    plan = services.settings_file.plan(body.voice)
    if plan is None:
        return SettingsLookedAt(voice=None)
    return SettingsLookedAt(
        voice=VoicePlan(
            tier=plan.tier.id if plan.tier else None,
            name=plan.tier.name if plan.tier else None,
            set_up=plan.set_up,
            download_bytes=plan.download_bytes,
            sources=sources_of(plan.tier) if plan.tier and plan.set_up else [],
            note=plan.note,
        )
    )


@router.post(
    "/settings-file",
    operation_id="settings.bring_in_file",
    response_model=SettingsBroughtIn,
    openapi_extra=INTERNAL,
)
def bring_in_settings(body: SettingsToBringIn, services: ServicesDep) -> SettingsBroughtIn:
    brought = services.settings_file.bring_in(
        learning=body.learning, voice=body.voice, set_up_voice=body.set_up_voice
    )
    return SettingsBroughtIn(
        notes=brought.notes,
        setting_up=schemas.Job.model_validate(brought.setting_up) if brought.setting_up else None,
    )
