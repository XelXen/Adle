"""The Expressive voice, put together from parts (ADR-062).

Who reads a lesson in the Expressive voice is a description the voice is made from
(ADR-057). A learner can write it in their own words, which is the most exact way, or say
what it is made of, a part at a time: who speaks, how old they sound, how high, how fast, the
color of the voice, its feeling, how steady it is, its accent, and what kind of speaker it
is. The parts, and the words of each, are those the voice's makers say it listens for
(gender, age, pitch, speech rate, emotion, timbre, use case); an accent is not among them,
and is asked for all the same: a sample says whether it was heard.

Pure. The description is written here and nowhere else, so that the same parts always make
the same voice: a recording is named by the description it was made from.
"""

from __future__ import annotations

from dataclasses import dataclass

from adle_core.voice.catalog import DEFAULT_DESIGN


@dataclass(frozen=True, slots=True)
class Option:
    key: str
    #: As the learner sees it.
    name: str
    #: As the voice is told.
    phrase: str


@dataclass(frozen=True, slots=True)
class Part:
    key: str
    name: str
    options: tuple[Option, ...]

    def option(self, key: str) -> Option | None:
        return next((option for option in self.options if option.key == key), None)


#: In the order they are shown. A part the learner leaves alone is left to the voice.
PARTS: tuple[Part, ...] = (
    Part(
        "speaker",
        "Speaker",
        (Option("woman", "Woman", "woman"), Option("man", "Man", "man")),
    ),
    Part(
        "age",
        "Age",
        (
            Option("young", "Young", "young"),
            Option("middle", "Middle-aged", "middle-aged"),
            Option("older", "Older", "elderly"),
        ),
    ),
    Part(
        "pitch",
        "Pitch",
        (
            Option("high", "High", "high-pitched"),
            Option("medium", "Medium", "mid-pitched"),
            Option("low", "Low", "low-pitched"),
        ),
    ),
    Part(
        "pace",
        "Pace",
        (
            Option("slow", "Slow", "a slow pace"),
            Option("medium", "Medium", "a medium pace"),
            Option("fast", "Fast", "a fast pace"),
        ),
    ),
    Part(
        "tone",
        "Tone",
        (
            Option("clear", "Clear", "crisp, clear"),
            Option("deep", "Deep", "deep"),
            Option("warm", "Warm", "warm, mellow"),
            Option("sweet", "Sweet", "sweet"),
            Option("rich", "Rich", "rich, magnetic"),
            Option("raspy", "Raspy", "slightly raspy"),
            Option("strong", "Strong", "powerful"),
        ),
    ),
    Part(
        "feeling",
        "Feeling",
        (
            Option("calm", "Calm", "calm"),
            Option("cheerful", "Cheerful", "cheerful"),
            Option("enthusiastic", "Enthusiastic", "enthusiastic"),
            Option("gentle", "Gentle", "gentle"),
            Option("serious", "Serious", "serious"),
            Option("lively", "Lively", "lively"),
            Option("soothing", "Soothing", "soothing"),
        ),
    ),
    Part(
        "steadiness",
        "Delivery",
        (
            Option("steady", "Steady", "a steady, even tone"),
            Option("varied", "Expressive", "expressive, varied intonation"),
        ),
    ),
    Part(
        "accent",
        "Accent",
        (
            Option("american", "American", "American"),
            Option("british", "British", "British"),
            Option("australian", "Australian", "Australian"),
            Option("indian", "Indian", "Indian"),
            Option("irish", "Irish", "Irish"),
            Option("scottish", "Scottish", "Scottish"),
        ),
    ),
    Part(
        "style",
        "Style",
        (
            Option("teacher", "Classroom teacher", "a patient classroom teacher"),
            Option("storyteller", "Storyteller", "a storyteller reading aloud"),
            Option("news", "Newsreader", "a newsreader"),
            Option("documentary", "Documentary narrator", "a documentary narrator"),
            Option("podcast", "Podcast host", "a friendly podcast host"),
            Option("presenter", "Presenter", "an upbeat presenter"),
            Option("coach", "Coach", "an encouraging coach"),
        ),
    ),
)

_PART = {part.key: part for part in PARTS}


@dataclass(frozen=True, slots=True)
class Preset:
    name: str
    #: What it is made of: nothing at all is Adle's own voice.
    parts: tuple[tuple[str, str], ...]


#: Voices to start from: each a choice of parts, which the learner can go on changing.
PRESETS: tuple[Preset, ...] = (
    Preset("Adle’s own", ()),
    Preset(
        "Calm narrator",
        (
            ("speaker", "man"),
            ("age", "middle"),
            ("pitch", "low"),
            ("pace", "slow"),
            ("tone", "deep"),
            ("feeling", "calm"),
            ("steadiness", "steady"),
            ("style", "documentary"),
        ),
    ),
    Preset(
        "Bright and lively",
        (
            ("speaker", "woman"),
            ("age", "young"),
            ("pace", "fast"),
            ("tone", "clear"),
            ("feeling", "lively"),
            ("steadiness", "varied"),
            ("accent", "american"),
        ),
    ),
    Preset(
        "Gentle storyteller",
        (
            ("pace", "slow"),
            ("tone", "warm"),
            ("feeling", "gentle"),
            ("steadiness", "varied"),
            ("style", "storyteller"),
        ),
    ),
    Preset(
        "British lecturer",
        (
            ("age", "middle"),
            ("pitch", "medium"),
            ("pace", "medium"),
            ("tone", "clear"),
            ("feeling", "serious"),
            ("accent", "british"),
            ("style", "teacher"),
        ),
    ),
    Preset(
        "Newsreader",
        (
            ("pace", "medium"),
            ("tone", "clear"),
            ("feeling", "serious"),
            ("steadiness", "steady"),
            ("style", "news"),
        ),
    ),
    Preset(
        "Encouraging coach",
        (
            ("pitch", "medium"),
            ("pace", "fast"),
            ("tone", "strong"),
            ("feeling", "enthusiastic"),
            ("steadiness", "varied"),
            ("style", "coach"),
        ),
    ),
)


class UnknownPartError(ValueError):
    """A part, or a choice of one, that is not offered."""


def checked(parts: dict[str, str] | None) -> dict[str, str]:
    """The parts chosen, in the order parts are shown, each a choice that is offered. A part
    given as an empty choice is one left to the voice."""
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


def _phrase(parts: dict[str, str], key: str) -> str:
    option = _PART[key].option(parts.get(key, ""))
    return option.phrase if option else ""


def _article(words: str) -> str:
    return "An" if words[:1].lower() in "aeiou" else "A"


def compose(parts: dict[str, str] | None) -> str:
    """The description a voice of these parts is made from. No parts at all: Adle's own."""
    chosen = checked(parts)
    if not chosen:
        return DEFAULT_DESIGN
    who = " ".join(
        word
        for word in (
            _phrase(chosen, "feeling"),
            _phrase(chosen, "age"),
            _phrase(chosen, "speaker") or "speaker",
        )
        if word
    )
    color = ", ".join(word for word in (_phrase(chosen, "pitch"), _phrase(chosen, "tone")) if word)
    sentence = f"{_article(who)} {who} with a {color or 'clear'} voice"
    steadiness = _phrase(chosen, "steadiness")
    if steadiness:
        sentence += f" and {steadiness}"
    accent = _phrase(chosen, "accent")
    english = f"{accent} English" if accent else "natural English"
    sentence += f", speaking {english} at {_phrase(chosen, 'pace') or 'an easy pace'}"
    style = _phrase(chosen, "style")
    if style:
        sentence += f", like {style}"
    return sentence + "."


def parts_of(stored: object, design: str) -> dict[str, str]:
    """The parts a description was made of, if it still is what they make: a description
    the learner has since written over, or one made by other words than today's, is its
    own words and no parts."""
    if not isinstance(stored, dict):
        return {}
    try:
        chosen = checked({str(key): str(value) for key, value in stored.items()})
    except UnknownPartError:
        return {}
    return chosen if chosen and compose(chosen) == design else {}
