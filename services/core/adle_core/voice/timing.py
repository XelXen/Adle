"""How fast a natural voice is on this computer, and what that means for a lesson (ADR-052).

Pure: no files and no clock. ``NarrationService`` measures, keeps the numbers beside the
voice, and asks these rules.

Nobody knows how strong the learner's computer is. Every voice, the lightest too, is timed
where it runs: once when it is set up, by saying as much as a lesson's first part from an
engine started cold, and then by every line it records. A voice faster than speech keeps
ahead of a learner once a lesson's first part can be heard. A voice slower than speech
falls behind one, so a lesson in it is ready only when enough of it is recorded that the
rest will be by the time the learner reaches it.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Characters said in a second of speech (measured, 2026-11-23: Kokoro 15.5, Qwen3-TTS
#: 14.0): how long a line not recorded yet will be, guessed by its length.
CHARS_PER_SECOND = 14.0
#: At least this much speech in all, for a lesson whose later parts are not written yet
#: (three real lessons said 89, 173 and 179 s).
LESSON_SPEECH = 120.0
#: More lead than the least that would do, for a voice slower on one line than another.
MARGIN = 1.15
#: The weight of what was just measured in a running mean.
WEIGHT = 0.4

#: What a voice says at setup to be timed: about as much as a lesson's first part.
SETUP_LINES = (
    "Let us begin with something you can see.",
    "Watch what happens to it, one step at a time, and listen for the words that change "
    "the picture.",
    "Then we will give it a name, and write down the rule it follows.",
)


@dataclass(frozen=True, slots=True)
class VoiceTiming:
    """What has been measured of one voice on this computer."""

    #: From a lesson asked for to its being ready, as lessons made here took (seconds).
    ready: float | None = None
    #: From an engine started cold to a lesson's first part said, timed at setup (seconds).
    start: float | None = None
    #: Seconds of work for each second of speech, once its models are loaded.
    rate: float | None = None


def mean(before: float | None, now: float) -> float:
    """A running mean: what was measured before, moved toward what was just measured."""
    return now if before is None else (1 - WEIGHT) * before + WEIGHT * now


def speech_of(text: str) -> float:
    """About how long a line takes to say, in seconds."""
    return len(text) / CHARS_PER_SECOND


def kept_ahead(rate: float | None, heard: float, lesson: float) -> bool:
    """Whether a learner who starts now can listen to the end without waiting for the voice.

    The voice records ``1 / rate`` seconds of speech each second while the learner hears
    one; with ``heard`` seconds recorded, from the start, of ``lesson`` in all, the learner
    never catches up with it if ``heard >= lesson * (1 - 1 / rate)``. A voice faster than
    speech keeps ahead once anything can be heard. Not yet measured, a voice is taken to be
    as fast as it was where Adle was made, which is faster than speech."""
    if rate is None or rate <= 1.0:
        return True
    return heard >= MARGIN * lesson * (1.0 - 1.0 / rate)


def ready_after(timing: VoiceTiming, guess: float) -> float:
    """About how long after a lesson is asked for it is ready in this voice, in seconds: as
    lessons made here took; else from the setup's timing, with the lead a voice slower than
    speech needs; else as usual where Adle was made."""
    if timing.ready is not None:
        return timing.ready
    if timing.start is not None:
        lead = 0.0
        if timing.rate is not None and timing.rate > 1.0:
            # The speech it must have recorded before the learner starts, at its rate.
            lead = timing.rate * MARGIN * LESSON_SPEECH * (1.0 - 1.0 / timing.rate)
        return timing.start + lead
    return guess


def read_timing(raw: object) -> VoiceTiming:
    """One voice's timing as kept (a number alone was the time to ready, before ADR-052)."""
    if isinstance(raw, int | float) and not isinstance(raw, bool) and raw > 0:
        return VoiceTiming(ready=float(raw))
    if not isinstance(raw, dict):
        return VoiceTiming()

    def number(key: str) -> float | None:
        value = raw.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
            return float(value)
        return None

    return VoiceTiming(ready=number("ready"), start=number("start"), rate=number("rate"))


def kept(timing: VoiceTiming) -> dict[str, float]:
    """One voice's timing as it is written down."""
    found = {"ready": timing.ready, "start": timing.start, "rate": timing.rate}
    return {key: round(value, 3) for key, value in found.items() if value is not None}
