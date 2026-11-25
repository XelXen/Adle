"""The natural voice, and a lesson's narration recorded in it (ADR-042).

The interface asks whether the voice is set up and which is chosen, chooses, sets a size up
or takes it away, asks for a sample of a voice (ADR-057), asks for a lesson's lines to be
recorded, and fetches what has been: each line with where its words are, and each clip as
sound. A clip is named by the core and never by a path.
"""

from __future__ import annotations

import base64
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints

from adle_core.api import schemas
from adle_core.application.narration import KIND_NARRATION
from adle_core.application.services import Services, get_services
from adle_core.voice import design as voice_design
from adle_core.voice.catalog import (
    MAX_DESIGN_CHARACTERS,
    TIERS,
    Tier,
    download_size,
    program_bytes,
)
from adle_core.voice.install import torch_index

router = APIRouter(tags=["voice"])

ServicesDep = Annotated[Services, Depends(get_services)]


class VoiceSpeaker(BaseModel):
    id: str
    name: str
    description: str


TierId = Literal["kokoro", "expressive"]
#: A learner's description of the Expressive voice: empty for Adle's own (ADR-057).
Design = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_DESIGN_CHARACTERS)]


#: The parts of a voice a learner chose (ADR-062): a part's key, then the key of its
#: choice. A part left out, or given as nothing, is left to the voice.
DesignParts = Annotated[
    dict[
        Annotated[str, StringConstraints(max_length=20)],
        Annotated[str, StringConstraints(max_length=20)],
    ],
    Field(max_length=12),
]


class VoiceDesignPreset(BaseModel):
    """A voice to start from: a choice of parts, and the description they make."""

    name: str
    text: str
    parts: dict[str, str]


class VoiceDesignOption(BaseModel):
    key: str
    name: str


class VoiceDesignPart(BaseModel):
    """One thing about a voice a learner can choose: who speaks, how fast, and so on."""

    key: str
    name: str
    options: list[VoiceDesignOption]


class VoiceDescriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: DesignParts


class VoiceDescription(BaseModel):
    """The description a voice of some parts is made from."""

    text: str


class VoiceRecording(BaseModel):
    """A lesson being recorded in the voice chosen now (ADR-057)."""

    lesson_id: str
    title: str
    #: Its lines recorded, and its lines in all.
    done: int
    total: int


class VoiceTier(BaseModel):
    """One size of natural voice, from the lightest (Kokoro) to the richest (Qwen3-TTS 1.7B)."""

    id: TierId
    name: str
    description: str
    #: What has to be downloaded for it: its models, and the aligner if it needs one. The
    #: programs it runs with come on top.
    model_bytes: int
    #: About what its programs come to, downloaded.
    program_bytes: int
    #: Where a setup downloads from, as a person would name each place.
    sources: list[str]
    #: The least memory on an NVIDIA graphics card it runs in; none for one that runs on the
    #: processor.
    min_memory_gb: float | None
    #: Its voices to choose from; none for a voice designed for each lesson.
    speakers: list[VoiceSpeaker]
    #: It is on this computer, whole.
    ready: bool
    #: It runs on this computer.
    fits: bool
    #: Why it does not, in a sentence, when it does not.
    why: str
    #: How it compares with speech on this computer, once it has been timed here: a voice
    #: slower than speech makes a lesson wait longer before it can start (ADR-052).
    speed: Literal["faster", "slower"] | None = None


class VoiceStatus(BaseModel):
    tiers: list[VoiceTier]
    #: The one lessons are read in, when there is one.
    tier: TierId | None
    #: Lessons are read in it. False when the learner turned it off, or there is none.
    enabled: bool
    #: The voice chosen for each size that has voices to choose from, by the size's id.
    speakers: dict[str, str]
    #: The richest size this computer runs: the one to offer first.
    recommended: TierId | None
    #: The NVIDIA graphics card found, if any, as its driver names it.
    gpu: str | None
    #: Set up by a developer elsewhere: used as it is, never removed from here.
    borrowed: bool
    #: The setup under way, if one is: which size, and how far it has come.
    setting_up: schemas.Job | None
    #: Who reads the lessons in the Expressive voice, as the learner described them, or
    #: Adle's own; each lesson adds how it is delivered (ADR-057).
    design: str
    #: The parts that description was put together from (ADR-062): none for Adle's own
    #: voice, and none for a description in the learner's own words.
    design_parts: dict[str, str]
    #: The parts a voice can be put together from, in the order they are shown.
    design_choices: list[VoiceDesignPart]
    #: Voices to start from.
    design_presets: list[VoiceDesignPreset]
    #: The lessons being recorded now: in a voice just chosen, those the learner opened last.
    recording: list[VoiceRecording]


class VoiceSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: TierId


class VoiceChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool | None = None
    tier: TierId | None = None
    speaker: Annotated[str, StringConstraints(max_length=40)] | None = None
    design: Design | None = None
    #: The Expressive voice by its parts: the core writes the description from them.
    parts: DesignParts | None = None


class VoiceSampleRequest(BaseModel):
    """A few words in a voice set up here: a speaker of a size, or the Expressive voice of a
    description or of parts (the one chosen when neither is given)."""

    model_config = ConfigDict(extra="forbid")
    tier: TierId
    speaker: Annotated[str, StringConstraints(max_length=40)] | None = None
    design: Design | None = None
    parts: DesignParts | None = None


class NarrationWord(BaseModel):
    #: Where the word is in the line, in characters.
    index: int
    length: int
    #: When it is said in the clip, in seconds.
    start: float
    end: float


class NarrationLine(BaseModel):
    #: The words, exactly as the lesson says them.
    text: str
    clip: str
    seconds: float
    words: list[NarrationWord]


class Narration(BaseModel):
    """What of a lesson has been recorded in the voice chosen now, and the recording under way."""

    lines: list[NarrationLine]
    recording: schemas.Job | None


class NarrationClip(BaseModel):
    #: ``audio/ogg`` or ``audio/wav``.
    mime: str
    #: The sound, in base 64.
    data: str


def sources_of(tier: Tier) -> list[str]:
    """Where setting a size up downloads from: its models from Hugging Face, its programs
    from the Python Package Index, torch (and Qwen3-TTS's aligner) from PyTorch, and the
    English model Kokoro reads words with from GitHub."""
    found = ["Hugging Face", "the Python Package Index"]
    if torch_index(tier.family) is not None or tier.aligned:
        found.append("PyTorch")
    if tier.family == "kokoro":
        found.append("GitHub")
    return found


def _speed(services: Services, tier: Tier) -> Literal["faster", "slower"] | None:
    rate = services.narration.timing(tier.id).rate
    if rate is None:
        return None
    return "faster" if rate <= 1.0 else "slower"


def _status(services: Services) -> VoiceStatus:
    status = services.narration.status()
    fits = services.narration.fits()
    setup = services.narration.setting_up()
    return VoiceStatus(
        tiers=[
            VoiceTier(
                id=tier.id,
                name=tier.name,
                description=tier.description,
                model_bytes=download_size(tier),
                program_bytes=program_bytes(tier.family),
                sources=sources_of(tier),
                min_memory_gb=tier.min_memory_gb,
                speakers=[
                    VoiceSpeaker(id=item.id, name=item.name, description=item.description)
                    for item in tier.speakers
                ],
                ready=tier.id in status.ready,
                fits=fits[tier.id].fits,
                why=fits[tier.id].why,
                speed=_speed(services, tier),
            )
            for tier in TIERS
        ],
        tier=cast(TierId | None, status.tier),
        enabled=status.enabled,
        speakers=status.speakers,
        recommended=cast(TierId | None, services.narration.recommended()),
        gpu=services.narration.hardware().gpu,
        borrowed=status.borrowed,
        setting_up=schemas.Job.model_validate(setup) if setup else None,
        design=status.design,
        design_parts=status.design_parts,
        design_choices=[
            VoiceDesignPart(
                key=part.key,
                name=part.name,
                options=[
                    VoiceDesignOption(key=option.key, name=option.name) for option in part.options
                ],
            )
            for part in voice_design.PARTS
        ],
        design_presets=[
            VoiceDesignPreset(
                name=preset.name,
                text=voice_design.compose(dict(preset.parts)),
                parts=dict(preset.parts),
            )
            for preset in voice_design.PRESETS
        ],
        recording=[
            VoiceRecording(
                lesson_id=item.lesson_id, title=item.title, done=item.done, total=item.total
            )
            for item in services.narration.recordings()
        ],
    )


@router.get("/voice", operation_id="voice.status", response_model=VoiceStatus)
def voice_status(services: ServicesDep) -> VoiceStatus:
    return _status(services)


@router.put("/voice", operation_id="voice.choose", response_model=VoiceStatus)
def choose_voice(body: VoiceChoice, services: ServicesDep) -> VoiceStatus:
    services.narration.choose(
        enabled=body.enabled,
        tier=body.tier,
        speaker=body.speaker,
        design=body.design,
        parts=body.parts,
    )
    return _status(services)


@router.post("/voice/design", operation_id="voice.describe", response_model=VoiceDescription)
def describe_voice(body: VoiceDescriptionRequest, services: ServicesDep) -> VoiceDescription:
    """The description a voice of these parts is made from (ADR-062): written by the core,
    so that the same parts are always the same voice. Nothing is changed."""
    return VoiceDescription(text=services.narration.describe(body.parts))


@router.post(
    "/voice/samples", operation_id="voice.sample", response_model=schemas.Job, status_code=202
)
def sample_voice(body: VoiceSampleRequest, services: ServicesDep) -> schemas.Job:
    """A sample of a voice, made in the background, once (ADR-057): the job's result names it."""
    return schemas.Job.model_validate(
        services.narration.sample(
            body.tier, speaker=body.speaker, design=body.design, parts=body.parts
        )
    )


@router.get("/voice/samples/{name}", operation_id="voice.sample_clip", response_model=NarrationClip)
def voice_sample(name: str, services: ServicesDep) -> NarrationClip:
    data, mime = services.narration.sample_clip(name)
    return NarrationClip(mime=mime, data=base64.b64encode(data).decode("ascii"))


@router.post(
    "/voice/setup", operation_id="voice.install", response_model=schemas.Job, status_code=202
)
def install_voice(body: VoiceSetup, services: ServicesDep) -> schemas.Job:
    """Set a size of voice up: it is downloaded, at the learner's word (ADR-042)."""
    return schemas.Job.model_validate(services.narration.install(body.tier))


@router.delete("/voice/{tier}", operation_id="voice.remove", response_model=VoiceStatus)
def remove_voice(tier: str, services: ServicesDep) -> VoiceStatus:
    services.narration.remove(tier)
    return _status(services)


@router.get(
    "/lessons/{lesson_id}/narration", operation_id="narration.get", response_model=Narration
)
def lesson_narration(lesson_id: str, services: ServicesDep) -> Narration:
    recording = services.jobs.find_active(KIND_NARRATION, lesson_id)
    return Narration(
        lines=[
            NarrationLine(
                text=line.text,
                clip=line.clip,
                seconds=line.seconds,
                words=[NarrationWord.model_validate(word) for word in line.words],
            )
            for line in services.narration.clips(lesson_id)
        ],
        recording=schemas.Job.model_validate(recording) if recording else None,
    )


@router.post(
    "/lessons/{lesson_id}/narration",
    operation_id="narration.record",
    response_model=schemas.Job,
    status_code=202,
)
def record_narration(lesson_id: str, services: ServicesDep) -> schemas.Job:
    return schemas.Job.model_validate(services.narration.start(lesson_id))


@router.get(
    "/lessons/{lesson_id}/narration/{clip}",
    operation_id="narration.clip",
    response_model=NarrationClip,
)
def narration_clip(lesson_id: str, clip: str, services: ServicesDep) -> NarrationClip:
    data, mime = services.narration.clip(lesson_id, clip)
    return NarrationClip(mime=mime, data=base64.b64encode(data).decode("ascii"))
