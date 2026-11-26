"""The teacher a lesson is written by: its character (ADR-071).

A lesson's words are written by a model as a teacher would say them. Who that teacher is,
the learner can say, the way they say who reads the lessons in the Expressive voice
(ADR-062): a part at a time (their manner, what kind of teacher they are, how much they
joke, whether they tell a fun fact now and then, how formally they speak), from a teacher
to start from, or in their own words. Or the teacher is the Expressive voice's own person,
when that voice reads the lessons.

A character changes how a lesson is said, never what it teaches or how carefully: the
rules of every lesson still hold (``axioms.py``). Light moments and fun facts are rare
whatever the character, and never in place of the teaching.

Pure. The description is written here and nowhere else, so that the same parts always make
the same teacher.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

#: The most a teacher may be described in, in the learner's own words.
MAX_CHARACTER_LENGTH = 300

#: Adle's own teacher: what a lesson is written by when the learner says nothing.
DEFAULT_CHARACTER = (
    "A warm, patient teacher who loves the subject, speaking plainly, with a light, witty "
    "moment now and then and a fun fact now and then that belongs to the topic."
)


@dataclass(frozen=True, slots=True)
class Option:
    key: str
    #: As the learner sees it.
    name: str
    #: As the writer is told.
    phrase: str


@dataclass(frozen=True, slots=True)
class Part:
    key: str
    name: str
    options: tuple[Option, ...]

    def option(self, key: str) -> Option | None:
        return next((option for option in self.options if option.key == key), None)


#: In the order they are shown. A part the learner leaves alone is left to Adle's teacher.
PARTS: tuple[Part, ...] = (
    Part(
        "manner",
        "Manner",
        (
            Option("warm", "Warm", "warm"),
            Option("calm", "Calm", "calm"),
            Option("cheerful", "Cheerful", "cheerful"),
            Option("enthusiastic", "Enthusiastic", "enthusiastic"),
            Option("gentle", "Gentle", "gentle"),
            Option("serious", "Serious", "serious"),
            Option("lively", "Lively", "lively"),
        ),
    ),
    Part(
        "style",
        "Kind of teacher",
        (
            Option("teacher", "Classroom teacher", "classroom teacher"),
            Option("storyteller", "Storyteller", "storyteller"),
            Option("scientist", "Curious scientist", "scientist, curious about everything"),
            Option("coach", "Coach", "coach who cheers every step"),
            Option("guide", "Guide", "guide who walks beside the learner"),
            Option("host", "Podcast host", "podcast host"),
            Option("professor", "Professor", "professor"),
        ),
    ),
    Part(
        "humor",
        "Humor",
        (
            Option("none", "None", ""),
            Option("rare", "Now and then", "a light, witty moment now and then"),
            Option("playful", "Playful", "a playful wit"),
        ),
    ),
    Part(
        "facts",
        "Fun facts",
        (
            Option("none", "None", ""),
            Option("rare", "Now and then", "a fun fact now and then that belongs to the topic"),
        ),
    ),
    Part(
        "register",
        "Words",
        (
            Option("casual", "Casual", "in casual, everyday words"),
            Option("plain", "Plain", "plainly"),
            Option("formal", "Formal", "formally and precisely"),
        ),
    ),
)

_PART = {part.key: part for part in PARTS}


@dataclass(frozen=True, slots=True)
class Preset:
    name: str
    #: What it is made of: nothing at all is Adle's own teacher.
    parts: tuple[tuple[str, str], ...]


#: Teachers to start from: each a choice of parts, which the learner can go on changing.
PRESETS: tuple[Preset, ...] = (
    Preset("Adle’s own", ()),
    Preset(
        "Storyteller",
        (
            ("manner", "warm"),
            ("style", "storyteller"),
            ("humor", "rare"),
            ("facts", "rare"),
            ("register", "plain"),
        ),
    ),
    Preset(
        "Curious scientist",
        (
            ("manner", "enthusiastic"),
            ("style", "scientist"),
            ("humor", "rare"),
            ("facts", "rare"),
            ("register", "plain"),
        ),
    ),
    Preset(
        "Calm guide",
        (
            ("manner", "calm"),
            ("style", "guide"),
            ("humor", "none"),
            ("facts", "rare"),
            ("register", "plain"),
        ),
    ),
    Preset(
        "Playful coach",
        (
            ("manner", "lively"),
            ("style", "coach"),
            ("humor", "playful"),
            ("facts", "rare"),
            ("register", "casual"),
        ),
    ),
    Preset(
        "Thoughtful professor",
        (
            ("manner", "serious"),
            ("style", "professor"),
            ("humor", "none"),
            ("facts", "rare"),
            ("register", "formal"),
        ),
    ),
)


class UnknownPartError(ValueError):
    """A part, or a choice of one, that is not offered."""


def checked(parts: Mapping[str, str] | None) -> dict[str, str]:
    """The parts chosen, in the order parts are shown, each a choice that is offered. A part
    given as an empty choice is one left to Adle's teacher."""
    given = dict(parts or {})
    found: dict[str, str] = {}
    for part in PARTS:
        choice = given.pop(part.key, "")
        if not choice:
            continue
        if part.option(choice) is None:
            raise UnknownPartError(part.key)
        found[part.key] = choice
    if given:
        raise UnknownPartError(next(iter(given)))
    return found


def _phrase(parts: Mapping[str, str], key: str, default: str) -> str:
    option = _PART[key].option(parts.get(key, ""))
    return option.phrase if option else default


def compose(parts: Mapping[str, str] | None) -> str:
    """The teacher these parts make, in a sentence. No parts at all: Adle's own. A part left
    alone is Adle's teacher's: warm, a classroom teacher, plain words, a light moment and a
    fun fact now and then."""
    chosen = checked(parts)
    if not chosen:
        return DEFAULT_CHARACTER
    who = f"{_phrase(chosen, 'manner', 'warm')} {_phrase(chosen, 'style', 'classroom teacher')}"
    article = "An" if who[:1].lower() in "aeiou" else "A"
    sentence = f"{article} {who}, speaking {_phrase(chosen, 'register', 'plainly')}"
    # What this teacher never does is said too: a lesson has a light moment or a fun fact
    # two or three times, as its teacher allows (ADR-075).
    never = [
        said
        for key, said in (("humor", "never jokes"), ("facts", "tells no fun facts"))
        if chosen.get(key) == "none"
    ]
    if never:
        sentence += ", who " + " and ".join(never)
    extras = [
        phrase
        for phrase in (
            _phrase(chosen, "humor", "a light, witty moment now and then"),
            _phrase(chosen, "facts", "a fun fact now and then that belongs to the topic"),
        )
        if phrase
    ]
    if extras:
        sentence += ", with " + " and ".join(extras)
    return sentence + "."


def described(words: str, parts: Mapping[str, str] | None) -> str:
    """The teacher a learner chose: in their own words when they wrote some, else what the
    parts make. Words are made one line and cut to the length they may have."""
    tidy = " ".join(words.split())[:MAX_CHARACTER_LENGTH]
    return tidy if tidy else compose(parts)


def following_voice(voice: str) -> str:
    """The teacher when the Expressive voice reads the lessons and the learner let the
    teacher follow it: the person that voice was described as."""
    who = " ".join(voice.split())[:MAX_CHARACTER_LENGTH]
    return (
        f"The person who reads the lesson aloud, as the learner described them: {who} "
        "Speak as they would, with a light, witty moment now and then and a fun fact now and "
        "then that belongs to the topic, where that suits them."
    )
