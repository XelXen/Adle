"""The core's part of a settings file (ADR-064): how the learner likes to learn, and the voice.

A settings file is put together and read by the desktop shell, which keeps what the core
never sees (the look of the app, which provider is chosen, the keys). This is the part the
core keeps: the learner's preferences, and which voice reads their lessons.

Bringing a file's settings in takes each on its own. One that this Adle does not know, or
that has a value it may not have, is left as it is here: a setting is never worth refusing
a file over. A voice that is not on this computer is set up (only when the learner said so,
having been told what is downloaded, ADR-042), or the nearest one this computer runs is
used, or the computer's own voice; and whichever it was is said.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from adle_core.application.jobs import JobSnapshot
from adle_core.application.learner import LearnerService
from adle_core.application.narration import NarrationService
from adle_core.errors import AdleError
from adle_core.learner_model.preferences import PREFERENCE_KEYS, from_stored
from adle_core.voice.catalog import DEFAULT_DESIGN, TIERS, Tier, download_size, program_bytes
from adle_core.voice.catalog import tier as find_tier

COMPUTER_VOICE = "the computer’s voice"


@dataclass(frozen=True, slots=True)
class VoicePlan:
    """What bringing a file's voice in would do on this computer."""

    #: The size of voice lessons would be read in; none for the computer's own.
    tier: Tier | None
    #: It is not on this computer yet: it has to be set up, which downloads it.
    set_up: bool
    #: Why it is not the one the file names, when it is not: a sentence for the learner.
    note: str = ""

    @property
    def download_bytes(self) -> int:
        if self.tier is None or not self.set_up:
            return 0
        return download_size(self.tier) + program_bytes(self.tier.family)


@dataclass(frozen=True, slots=True)
class SettingsBroughtIn:
    #: What could not be had as the file has it, and what was done instead.
    notes: list[str] = field(default_factory=list)
    #: A voice being set up because of it.
    setting_up: JobSnapshot | None = None


class SettingsFileService:
    def __init__(self, learner: LearnerService, narration: NarrationService) -> None:
        self._learner = learner
        self._narration = narration

    def save(self) -> dict[str, dict[str, Any]]:
        """What the core keeps of the learner's settings, as a file holds it."""
        status = self._narration.status()
        return {
            "learning": dict(self._learner.get_preferences().to_stored()),
            "voice": {
                "enabled": status.enabled,
                "tier": status.tier,
                "speakers": dict(status.speakers),
                # Adle's own voice is said by saying nothing: it may be worded anew later.
                "design": "" if status.design == DEFAULT_DESIGN else status.design,
                "parts": dict(status.design_parts),
            },
        }

    # -- the voice a file names, on this computer ----------------------------------------------

    def plan(self, voice: Mapping[str, Any] | None) -> VoicePlan | None:
        """What would read the lessons here if a file's voice were brought in. Nothing is
        changed. None when the file says nothing of a voice."""
        if voice is None:
            return None
        if voice.get("enabled") is False:
            # The computer's own voice, as the file says.
            return VoicePlan(None, set_up=False)
        named = voice.get("tier")
        wanted = find_tier(named) if isinstance(named, str) else None
        if wanted is None:
            # No voice named, or one this Adle does not know: which voice reads is left as
            # it is here.
            return None
        status = self._narration.status()
        fits = self._narration.fits()
        order = [tier.id for tier in TIERS]
        # The one named, then each lighter one, the nearest first.
        nearest = [wanted, *reversed(TIERS[: order.index(wanted.id)])]
        for candidate in nearest:
            note = (
                ""
                if candidate.id == wanted.id
                else f"The {wanted.name} voice can’t run on this computer, so the "
                f"{candidate.name} voice is used."
            )
            if candidate.id in status.ready:
                return VoicePlan(candidate, set_up=False, note=note)
            if fits[candidate.id].fits and not status.borrowed:
                return VoicePlan(candidate, set_up=True, note=note)
        return VoicePlan(
            None,
            set_up=False,
            note=(
                f"The {wanted.name} voice can’t run on this computer, so {COMPUTER_VOICE} is used."
            ),
        )

    # -- bringing a file's settings in ----------------------------------------------------------

    def bring_in(
        self,
        *,
        learning: Mapping[str, Any] | None,
        voice: Mapping[str, Any] | None,
        set_up_voice: bool,
    ) -> SettingsBroughtIn:
        notes: list[str] = []
        if learning is not None:
            self._bring_learning(learning)
        setting_up = self._bring_voice(voice, set_up_voice, notes) if voice is not None else None
        return SettingsBroughtIn(notes=notes, setting_up=setting_up)

    def _bring_learning(self, learning: Mapping[str, Any]) -> None:
        # Each preference the file has, if its value is one it may have: the others stay.
        # A value it may not have comes back from ``from_stored`` as the default, and so
        # not as it was written.
        usable = from_stored(learning)
        written = usable.to_stored()
        changed = {
            key: getattr(usable, key)
            for key in PREFERENCE_KEYS
            if key in learning and written[key] == learning[key]
        }
        if changed:
            self._learner.update_preferences(**changed)

    def _bring_voice(
        self, voice: Mapping[str, Any], set_up_voice: bool, notes: list[str]
    ) -> JobSnapshot | None:
        # Who reads in the Expressive voice: by its parts if it was made of parts, or else
        # in the words it was written in. Kept whether or not that voice runs here.
        parts, design = voice.get("parts"), voice.get("design")
        try:
            if isinstance(parts, dict) and parts:
                self._narration.choose(
                    parts={str(key): str(value) for key, value in list(parts.items())[:12]}
                )
            elif isinstance(design, str):
                self._narration.choose(design=design)
        except AdleError:
            notes.append("The Expressive voice’s description couldn’t be used, so it is as it was.")

        # The speaker of each voice that has speakers, if this Adle knows them.
        speakers = voice.get("speakers")
        if isinstance(speakers, dict):
            for tier in TIERS:
                speaker = speakers.get(tier.id)
                if isinstance(speaker, str) and speaker in {item.id for item in tier.speakers}:
                    self._narration.choose_speaker(tier.id, speaker)

        plan = self.plan(voice)
        if plan is None:
            return None
        if plan.note:
            notes.append(plan.note)
        if plan.tier is None:
            self._narration.choose(enabled=False)
            return None
        if not plan.set_up:
            self._narration.choose(tier=plan.tier.id, enabled=True)
            return None
        if not set_up_voice:
            notes.append(
                f"The {plan.tier.name} voice isn’t set up on this computer. "
                "Set it up in Settings to use it."
            )
            return None
        try:
            # It becomes the voice in use once it is set up (``NarrationService._install``).
            job = self._narration.install(plan.tier.id)
        except AdleError as error:
            notes.append(f"The {plan.tier.name} voice couldn’t be set up now. {error.message}")
            return None
        notes.append(
            f"The {plan.tier.name} voice is being set up. Lessons are read in it once it is ready."
        )
        return job
