"""What a learner has told Adle about how they like to learn.

Only explicit, non-sensitive choices are kept: pace, how much explanation, and
whether narration and captions are on. Adle never infers anything about who a
learner is (PLAN.md 8.1).

Preferences are stored as one row per key so that a value written by a newer
or older version of Adle can be ignored without losing the others.
"""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum

from adle_core.lessons import character

MAX_GOAL_LENGTH = 300
MAX_VOICE_LENGTH = 120


class Pace(StrEnum):
    RELAXED = "relaxed"
    STANDARD = "standard"
    BRISK = "brisk"


class ExplanationDensity(StrEnum):
    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


@dataclass(frozen=True, slots=True)
class LearnerPreferences:
    pace: Pace = Pace.STANDARD
    explanation_density: ExplanationDensity = ExplanationDensity.BALANCED
    #: Read lessons aloud.
    narration: bool = True
    #: Show the words of the narration as it plays.
    captions: bool = True
    #: The name of the voice to read with, as this computer lists it. Empty: choose one.
    voice: str = ""
    #: How loud narration is, from 0 (silent) to 100.
    volume: int = 100
    #: What the learner wants to get out of their study, in their own words.
    goal: str = ""
    #: The teacher who writes the lessons, in the learner's own words (ADR-071). Empty: the
    #: one ``character_parts`` make, or Adle's own.
    character: str = ""
    #: What that teacher is made of, a choice for each part chosen (``lessons/character``).
    character_parts: Mapping[str, str] = field(default_factory=dict)
    #: When the Expressive voice reads the lessons, the teacher is its person.
    character_follows_voice: bool = True

    def __post_init__(self) -> None:
        if len(self.goal) > MAX_GOAL_LENGTH:
            raise ValueError(f"A goal can be at most {MAX_GOAL_LENGTH} characters.")
        if len(self.voice) > MAX_VOICE_LENGTH:
            raise ValueError("That is not the name of a voice.")
        if not 0 <= self.volume <= 100:
            raise ValueError("Volume is a number from 0 to 100.")
        if len(self.character) > character.MAX_CHARACTER_LENGTH:
            raise ValueError("A teacher can be described in at most 300 characters.")

    def to_stored(self) -> dict[str, object]:
        """One JSON-serialisable value per preference key."""
        return {
            key: value.value
            if isinstance(value, StrEnum)
            else dict(value)
            if isinstance(value, Mapping)
            else value
            for key, value in asdict(self).items()
        }


DEFAULT_PREFERENCES = LearnerPreferences()
PREFERENCE_KEYS = tuple(field.name for field in fields(LearnerPreferences))


def from_stored(stored: Mapping[str, object]) -> LearnerPreferences:
    """Build preferences from stored values, falling back to the default for anything unusable.

    Unknown keys and values of the wrong kind are ignored rather than raised:
    a preference is never worth failing to open the app over.
    """
    values: dict[str, object] = {}
    pace = stored.get("pace")
    if isinstance(pace, str) and pace in Pace:
        values["pace"] = Pace(pace)
    density = stored.get("explanation_density")
    if isinstance(density, str) and density in ExplanationDensity:
        values["explanation_density"] = ExplanationDensity(density)
    for key in ("narration", "captions"):
        flag = stored.get(key)
        if isinstance(flag, bool):
            values[key] = flag
    goal = stored.get("goal")
    if isinstance(goal, str):
        values["goal"] = " ".join(goal.split())[:MAX_GOAL_LENGTH]
    voice = stored.get("voice")
    if isinstance(voice, str) and len(voice) <= MAX_VOICE_LENGTH:
        values["voice"] = voice
    volume = stored.get("volume")
    if isinstance(volume, int) and not isinstance(volume, bool) and 0 <= volume <= 100:
        values["volume"] = volume
    words = stored.get("character")
    if isinstance(words, str):
        values["character"] = " ".join(words.split())[: character.MAX_CHARACTER_LENGTH]
    parts = stored.get("character_parts")
    if isinstance(parts, dict) and all(
        isinstance(key, str) and isinstance(value, str) for key, value in parts.items()
    ):
        with contextlib.suppress(character.UnknownPartError):
            values["character_parts"] = character.checked(parts)
    follows = stored.get("character_follows_voice")
    if isinstance(follows, bool):
        values["character_follows_voice"] = follows
    return LearnerPreferences(**values)  # type: ignore[arg-type]
