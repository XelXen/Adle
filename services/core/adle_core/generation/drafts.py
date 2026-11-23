"""What a model is asked to write, and how it becomes something Adle can store.

A model is not asked for the Lesson IR. It is asked for a **draft**: a smaller,
forgiving shape with no identifiers, no bookkeeping, and no references it could
get wrong. This module compiles a draft into the IR deterministically:

* identifiers are assigned here, never read from the model;
* objectives and citations are looked up by the numbers the model was given,
  and a number that was not offered is dropped, so a citation cannot be invented;
* durations are computed from the words, not guessed by the model;
* harmless formatting habits (Markdown emphasis, ``\\( \\)`` mathematics) are
  normalised, and everything else is left for the IR's own validation to judge.

The result is still untrusted: it goes through ``lessons.bundle.parse_bundle``
like any other lesson.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from adle_core.generation.figures import FigureError, beat_seconds, compile_figure, undoubled
from adle_core.generation.slides import SlideError, compile_slide
from adle_core.generation.speech import spoken
from adle_core.lessons.ir import (
    MAX_BEATS,
    MAX_PRACTICE_ITEMS,
    MAX_SEGMENTS,
    MISCONCEPTION_KINDS,
    SCHEMA_VERSION,
    STRATEGIES,
    AssessmentItem,
    Display,
    LongDisplay,
    VoiceDescription,
)

logger = logging.getLogger(__name__)

#: A lesson asks for at most this many scenes: each one is a separate model request.
MAX_SCENES_PER_LESSON = 2
#: And has at most this many figures, which the core draws (ADR-045).
MAX_FIGURES_PER_LESSON = 8
#: And this many slides: a picture for every part that teaches (ADR-049), drawn by the core.
MAX_SLIDES_PER_LESSON = 12
#: The parts a figure may stand in.
_FIGURE_PARTS = ("explanation", "visualization", "interaction", "worked_example")
#: And a slide: every part that teaches, a summary among them.
_SLIDE_PARTS = (*_FIGURE_PARTS, "summary")
MAX_PROPOSED_CONCEPTS = 16
MAX_PROPOSED_OBJECTIVES = 4
READING_WORDS_PER_MINUTE = 150


class DraftError(ValueError):
    """The model's answer is not a usable draft. ``problems`` says what to fix."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


# -- reading the answer ---------------------------------------------------------

_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*[ \t]*\r?\n(.*?)```", re.DOTALL)


def extract_json_object(text: str) -> dict[str, Any]:
    """The one JSON object in a model's answer, with or without a code fence around it."""
    candidate = text.strip()
    fenced = _FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()
    if not candidate.startswith("{"):
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise DraftError(["The answer must be one JSON object and nothing else."])
        candidate = candidate[start : end + 1]
    try:
        value = json.loads(mend_backslashes(candidate))
    except ValueError as error:
        raise DraftError(
            [
                "The answer is not valid JSON. Check that every string is closed, that "
                "there is no comma after the last item of a list or an object, and that "
                "a quotation mark inside a string has a backslash before it."
            ]
        ) from error
    if not isinstance(value, dict):
        raise DraftError(["The answer must be one JSON object."])
    return value


# -- backslashes -------------------------------------------------------------------

#: The letters that make an escape JSON knows and that also begin commands of TeX:
#: ``\beta``, ``\frac``, ``\nu``, ``\rho``, ``\theta``.
_AMBIGUOUS_ESCAPES = frozenset("bfnrt")
#: Commands of TeX that begin with one of those letters and are long enough not to be a
#: line break or a tab followed by a word. Outside mathematics only these are taken for
#: TeX; inside it, any command is.
_TEX_COMMANDS = frozenset(
    {
        *("bar", "begin", "beta", "big", "bigg", "bigl", "bigr", "bigcap", "bigcup"),
        *("binom", "bmod", "boldsymbol", "bot", "boxed", "bullet"),
        *("frac", "forall"),
        *("nabla", "neg", "neq", "newline", "nmid", "not", "notin", "nleq", "ngeq"),
        *("nolimits", "nonumber"),
        *("rangle", "rbrace", "rbrack", "rceil", "rfloor", "rho", "right", "rightarrow"),
        *("rvert",),
        *("tan", "tanh", "tau", "text", "textbf", "textit", "textrm", "texttt", "tfrac"),
        *("theta", "therefore", "tilde", "times", "top", "triangle"),
    }
)
_FOUR_HEX = re.compile(r"[0-9a-fA-F]{4}")
_LETTERS = re.compile(r"[A-Za-z]+")


def _mathematics_after(following: str, in_math: bool) -> bool:
    r"""Whether ``\(`` or ``\[`` has opened mathematics, or ``\)`` or ``\]`` closed it."""
    if following in ("(", "["):
        return True
    if following in (")", "]"):
        return False
    return in_math


def mend_backslashes(text: str) -> str:
    r"""Make the backslashes of TeX safe inside the strings of a JSON answer.

    In JSON a backslash is written twice, and a model writing ``$\frac{1}{2}$`` often
    writes it once. Some of the results are not JSON at all (``\sigma``). The others are
    worse, because they are: ``\frac`` reads as a form feed followed by "rac" and
    ``\theta`` as a tab followed by "heta", and the lesson would show nonsense where its
    mathematics was, with nothing to say that anything had gone wrong.

    So before an answer is parsed, a backslash inside a string is doubled when it cannot
    be an escape of JSON, or when it begins a command of TeX: any command between dollar
    signs or after ``\(``, and a well-known one anywhere. A backslash that is already
    written twice is left alone, and so is a real ``\n`` between two sentences.
    """
    out: list[str] = []
    in_string = in_math = False
    index, end = 0, len(text)
    while index < end:
        char = text[index]
        if not in_string:
            in_string, in_math = char == '"', False
            out.append(char)
            index += 1
            continue
        if char != "\\":
            if char == '"':
                in_string = False
            elif char == "$":
                in_math = not in_math
            out.append(char)
            index += 1
            continue

        following = text[index + 1] if index + 1 < end else ""
        if following == "\\":
            # Written twice already. What follows the pair may open or close mathematics.
            in_math = _mathematics_after(text[index + 2] if index + 2 < end else "", in_math)
            out.append("\\\\")
            index += 2
            continue
        if following in ('"', "/"):
            out.append(char + following)
            index += 2
            continue
        if following == "u" and _FOUR_HEX.match(text, index + 2):
            out.append(text[index : index + 6])
            index += 6
            continue
        if following in _AMBIGUOUS_ESCAPES:
            word = _LETTERS.match(text, index + 1)
            command = word.group() if word else ""
            if len(command) < 2 or not (in_math or command in _TEX_COMMANDS):
                # A line break, a tab: an escape that means what JSON says it means.
                out.append(char + following)
                index += 2
                continue
        # TeX, or nothing JSON knows: the backslash is meant as itself.
        in_math = _mathematics_after(following, in_math)
        out.append("\\\\")
        index += 1
    return "".join(out)


def extract_python_file(text: str) -> str:
    """The Python file in a model's answer: the first fenced block, or the whole answer."""
    fenced = _FENCE.search(text)
    source = fenced.group(1) if fenced else text
    return source.strip() + "\n"


# -- tidying text ----------------------------------------------------------------

#: The two ways of writing mathematics that the lesson format does not use.
_PAREN_MATH = (("\\(", "\\)"), ("\\[", "\\]"))
#: Nothing a model writes for one field is longer than this; the lesson format's own limits
#: are far below it. What is past it is not tidied, and is refused by those limits.
MAX_TIDIED_CHARACTERS = 20_000
_HIDDEN_MARKS = re.compile("[\u202a-\u202e\u2066-\u2069\u200e\u200f\u061c\u2060\ufeff]")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_CODE = re.compile(r"`([^`]+)`")
_LIST_MARK = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _dollar_math(text: str) -> str:
    """Mathematics written as \\( ... \\) or \\[ ... \\], rewritten between dollar signs.

    One pass for each pair. A pattern that looks for "an opening, anything, a closing"
    starts over at every opening when there is no closing, and text made of openings
    alone would keep the whole service waiting; an opening with nothing to close it
    ends the search instead.
    """
    for opening, closing in _PAREN_MATH:
        if opening not in text:
            continue
        out: list[str] = []
        position = 0
        while True:
            start = text.find(opening, position)
            if start < 0:
                break
            end = text.find(closing, start + len(opening) + 1)
            if end < 0:
                break
            out.append(text[position:start])
            out.append("$" + text[start + len(opening) : end].strip() + "$")
            position = end + len(closing)
        out.append(text[position:])
        text = "".join(out)
    return text


def tidy(text: str) -> str:
    """Normalise the formatting habits of a model without changing what is said."""
    # Marks that change the direction text is drawn in, or hide in it. A model has no
    # reason to write one, and they can make a sentence read as something it is not.
    text = undoubled(_HIDDEN_MARKS.sub("", text))
    if len(text) > MAX_TIDIED_CHARACTERS:
        return " ".join(text.split())
    text = _dollar_math(text)
    text = _BOLD.sub(lambda match: match.group(1) or match.group(2), text)
    text = _CODE.sub(lambda match: match.group(1), text)
    text = _LIST_MARK.sub("", text)
    return " ".join(text.split())


def _text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = tidy(value)
    return cleaned or None


def _words(text: str) -> int:
    return len(text.split())


# -- the lesson draft ---------------------------------------------------------------


class _Draft(BaseModel):
    # Extra keys are ignored: a model that adds a comment field has not written a bad lesson.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class BeatDraft(_Draft):
    say: str = Field(min_length=1)
    show: str | None = None


class SceneDraft(_Draft):
    #: For whoever writes the scene: what to draw and how it changes.
    brief: str = Field(min_length=1, max_length=1500)
    #: The same thing in words, for a learner who cannot see the picture.
    description: str = Field(min_length=1)


class OptionDraft(_Draft):
    text: str = Field(min_length=1)
    correct: bool = False
    feedback: str | None = None
    misconception: str | None = None


class QuestionDraft(_Draft):
    form: str
    stem: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    hint: str | None = None
    #: Which of the concept's objectives this checks, counted from 1 as they were listed.
    objective: int | None = None
    difficulty: int = 2
    transfer: bool = False
    options: list[OptionDraft] = Field(default_factory=list)
    correct: bool | None = None
    answer: float | None = None
    tolerance: float | None = None
    unit: str | None = None
    accepted: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    rubric: list[str] = Field(default_factory=list)
    sample_answer: str | None = None


class SegmentDraft(_Draft):
    type: str
    #: Required, except where the core can name the part by what it is (``_UNTITLED``).
    title: str = ""
    beats: list[BeatDraft] = Field(default_factory=list)
    prompt: str | None = None
    problem: str | None = None
    scene: SceneDraft | None = None
    #: A figure: a kind of picture the core draws from this data (ADR-045). Read by the
    #: figures module; a field it does not know is passed over there.
    figure: dict[str, Any] | None = None
    #: A slide: what is on the stage and how it changes as the narration reaches the words
    #: in [brackets] (ADR-049). Read by the slides module.
    visual: dict[str, Any] | None = None
    question: QuestionDraft | None = None


class LessonHeaderDraft(_Draft):
    """What a lesson's answer says before its parts: enough to begin the lesson with its
    first part while the rest is written (ADR-048)."""

    title: str = Field(min_length=1)
    strategy: str = "visual"
    #: The numbers of the supplied passages the lesson draws on.
    sources: list[int] = Field(default_factory=list)
    #: How the narrator sounds, in a sentence. A lesson without one is read in Adle's own.
    voice: str | None = None


class LessonDraft(LessonHeaderDraft):
    segments: list[SegmentDraft] = Field(min_length=1)
    #: Questions that are not part of the lesson's flow, kept for practice and review.
    practice: list[QuestionDraft] = Field(default_factory=list)

    @field_validator("practice", mode="before")
    @classmethod
    def _usable_practice(cls, value: Any) -> Any:
        """A question kept for practice that is not whole is left out here, before it can
        cost the lesson: practice is extra, and never a reason to write a lesson again."""
        if not isinstance(value, list):
            return []
        kept = []
        for item in value:
            try:
                QuestionDraft.model_validate(item)
            except ValidationError:
                continue
            kept.append(item)
        return kept


@dataclass(frozen=True, slots=True)
class ObjectiveRef:
    id: str
    statement: str


@dataclass(frozen=True, slots=True)
class PassageRef:
    """A passage that was shown to the model, as the lesson may cite it."""

    source_id: str
    section_id: str
    source_name: str
    locator: str


@dataclass(frozen=True, slots=True)
class LessonContext:
    lesson_id: str
    course_id: str
    concept_id: str
    objectives: list[ObjectiveRef]
    #: In the order they were numbered in the prompt, starting at 1.
    passages: list[PassageRef] = field(default_factory=list)
    #: The way of teaching that was asked for. When set it is what the lesson records,
    #: whatever the draft says about itself.
    strategy: str | None = None


@dataclass(frozen=True, slots=True)
class SceneBrief:
    """One scene to be written: everything the scene writer is told."""

    scene_id: str
    segment_id: str
    kind: Literal["animation", "interactive"]
    title: str
    brief: str
    description: str
    narration: list[str]


@dataclass(frozen=True, slots=True)
class FigureScene:
    """One figure, drawn already: the scene file the core wrote for it."""

    scene_id: str
    segment_id: str
    kind: str
    title: str
    description: str
    source: str
    interactive: bool


@dataclass(frozen=True, slots=True)
class CompiledLesson:
    #: The lesson in IR form, not yet validated.
    lesson: dict[str, Any]
    scenes: list[SceneBrief]
    #: Drawn by the core (ADR-045): no request is needed for them.
    figures: list[FigureScene] = field(default_factory=list)
    #: How many figures the draft gave that could not be drawn as given.
    figures_dropped: int = 0


def _problems(error: ValidationError, prefix: str = "") -> list[str]:
    found = []
    for item in error.errors(include_input=False, include_url=False):
        where = ".".join(str(part) for part in item["loc"])
        message = str(item["msg"]).removeprefix("Value error, ")
        found.append(f"{prefix}{where}: {message}" if where else f"{prefix}{message}")
    return found[:12]


def parse_lesson_draft(data: dict[str, Any]) -> LessonDraft:
    try:
        return LessonDraft.model_validate(data)
    except ValidationError as error:
        raise DraftError(_problems(error)) from error


_SECONDS_FOR = {"checkpoint": 45, "interaction": 60, "reflection": 25}


#: The most a line on the board may hold (``Display`` in the Lesson IR).
MAX_BOARD_CHARACTERS = 600

#: Words of the narration a model marked in [brackets], while they are said in words:
#: characters nothing else writes, taken out again once the line is said (ADR-049).
_CUE_OPEN, _CUE_CLOSE = "\u27e6", "\u27e7"
#: Brackets that hold a number or an interval ("[0, 1]") are mathematics, not a cue.
_INTERVAL = re.compile(
    r"\s*[-+]?(?:\d+(?:\.\d+)?|\.\d+|infinity)\s*(?:,\s*[-+]?(?:\d+(?:\.\d+)?|\.\d+|infinity)\s*)?",
    re.IGNORECASE,
)


def _cue_end(text: str, start: int) -> int | None:
    """Where the bracket opened at ``start`` closes, outside any $...$ in it: None when it
    does not close within a phrase, or another opens first."""
    in_math = False
    for index in range(start + 1, min(len(text), start + 160)):
        char = text[index]
        if char == "$":
            in_math = not in_math
        elif not in_math and char == "[":
            return None
        elif not in_math and char == "]":
            return index
    return None


def _marked(text: str) -> str:
    """The words a model put in [brackets] to cue the next step of a part's picture,
    marked with characters nothing else writes. Brackets inside $...$, and brackets that
    hold a number or an interval, are left as they were written."""
    out: list[str] = []
    in_math = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "$":
            in_math = not in_math
        elif char == "[" and not in_math:
            end = _cue_end(text, index)
            inner = text[index + 1 : end] if end is not None else ""
            if end is not None and inner.strip() and not _INTERVAL.fullmatch(inner):
                out.append(_CUE_OPEN + inner + _CUE_CLOSE)
                index = end + 1
                continue
        out.append(char)
        index += 1
    return "".join(out)


def _cued(text: str) -> tuple[str, list[int]]:
    """A line as it is said, without its marks, and where each marked phrase begins."""
    clean: list[str] = []
    cues: list[int] = []
    for char in text:
        if char == _CUE_OPEN:
            cues.append(len(clean))
        elif char == _CUE_CLOSE or (char.isspace() and (not clean or clean[-1] == " ")):
            continue
        else:
            clean.append(" " if char.isspace() else char)
    said = "".join(clean).rstrip()
    found = sorted({cue for cue in cues if cue < len(said)})
    return said, found


def _narration(beats: list[BeatDraft]) -> list[dict[str, Any]]:
    """What is said, line by line, with where each cue stands in it (``cues``) and the
    line put on the board as it begins (``show``)."""
    narration = []
    previous: str | None = None
    for beat in beats[:MAX_BEATS]:
        # Narration is read aloud: notation in it is said in words (generation/speech.py).
        said, cues = _cued(spoken(_marked(tidy(beat.say))))
        entry: dict[str, Any] = {"text": said}
        if cues:
            entry["cues"] = cues
        shown = _text(beat.show)
        # A line on the board whose mathematics is not closed, or that is too long to show,
        # is left off: the words said over it stay, and a lesson is not written again for
        # one line of its board (ADR-047). Anything else wrong with it is still refused.
        # The same line twice in a row is shown once (a real lesson's board repeated its
        # line three times, 2026-11-22).
        if (
            shown
            and shown.count("$") % 2 == 0
            and len(shown) <= MAX_BOARD_CHARACTERS
            and shown != previous
        ):
            entry["show"] = shown
        previous = shown or previous
        narration.append(entry)
    return narration


def _sentence_starts(
    narration: list[dict[str, Any]], after: tuple[int, int]
) -> list[tuple[int, int]]:
    """Where each sentence of the narration begins, after a place in it."""
    starts: list[tuple[int, int]] = []
    for line, beat in enumerate(narration):
        said = beat["text"]
        heads = [0] + [match.end() for match in re.finditer(r"[.?!;:]\s+(?=\S)", said)]
        starts += [
            (line, head)
            for head in heads
            if (line, head) > after and (line, head) != (0, 0) and head < len(said)
        ]
    return starts


def _paced(narration: list[dict[str, Any]], steps: int) -> list[dict[str, Any]]:
    """The narration's cues fitted to a slide of ``steps`` steps: one cue for each step
    after the first, which plays as the part begins. A model that marked the first step
    too has that mark dropped, and marks past the last step are dropped. Steps that have
    no mark are cued where a sentence begins, spread over what is said after the last
    mark, or, short of sentences, at words of the last line."""
    wanted = max(0, steps - 1)
    places = [(line, cue) for line, beat in enumerate(narration) for cue in beat.get("cues", [])]
    if len(places) > wanted and places and places[0] == (0, 0):
        places = places[1:]
    if len(places) > wanted and len(places) == steps:
        places = places[1:]
    places = places[:wanted]
    missing = wanted - len(places)
    if missing > 0:
        starts = _sentence_starts(narration, places[-1] if places else (0, 0))
        if len(starts) >= missing:
            if missing == 1:
                places.append(starts[len(starts) // 2])
            else:
                places += [
                    starts[round(index * (len(starts) - 1) / (missing - 1))]
                    for index in range(missing)
                ]
        else:
            places += starts
            last = len(narration) - 1
            words = [match.start() for match in re.finditer(r"\S+", narration[last]["text"])]
            still = wanted - len(places)
            for number in range(1, still + 1):
                if words:
                    places.append(
                        (last, words[min(len(words) - 1, number * len(words) // (still + 1))])
                    )
    paced = [{key: value for key, value in beat.items() if key != "cues"} for beat in narration]
    for line, cue in sorted(set(places)):
        paced[line].setdefault("cues", []).append(cue)
    return paced


#: How fast the words a slide's step goes with are taken to be said when its animations
#: are fitted to them (ADR-055): brisker than most voices, so that a step is over first.
_BRISK_WORDS_PER_SECOND = 3.0
#: The pause between two lines said one after the other.
_LINE_PAUSE_SECONDS = 0.3
#: How long the last step may go on after the last word is said.
_LAST_STEP_AFTER_SECONDS = 0.6


def _step_seconds(narration: list[dict[str, Any]], steps: int) -> list[float]:
    """How long each step of a slide has before the next begins: the words from where it is
    cued (the first from the start) to where the next one is, said briskly; the last has to
    the end of what is said, and a moment more."""
    if not narration or steps <= 0:
        return []
    cues = sorted(
        (line, cue) for line, beat in enumerate(narration) for cue in beat.get("cues", [])
    )
    starts = [(0, 0), *cues][:steps]
    end = (len(narration) - 1, len(narration[-1]["text"]))
    seconds: list[float] = []
    for index, (line, char) in enumerate(starts):
        to_line, to_char = starts[index + 1] if index + 1 < len(starts) else end
        words = 0
        for at in range(line, to_line + 1):
            text = narration[at]["text"]
            begin = char if at == line else 0
            stop = to_char if at == to_line else len(text)
            words += len(text[begin:stop].split())
        seconds.append(words / _BRISK_WORDS_PER_SECOND + (to_line - line) * _LINE_PAUSE_SECONDS)
    seconds[-1] += _LAST_STEP_AFTER_SECONDS
    return seconds


def _uncued(narration: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The narration of a part with no slide: its cues have nothing to move."""
    return [{key: value for key, value in beat.items() if key != "cues"} for beat in narration]


def minutes_for(segments: Sequence[Mapping[str, Any]]) -> int:
    """How long a lesson is said to take, from its parts: whole minutes, one to sixty."""
    total = sum(int(segment.get("estimated_seconds", 0)) for segment in segments)
    return max(1, min(60, math.ceil(total / 60)))


def _seconds(kind: str, narration: list[dict[str, Any]]) -> int:
    spoken = sum(_words(beat["text"]) for beat in narration)
    reading = math.ceil(spoken / READING_WORDS_PER_MINUTE * 60)
    return max(10, min(900, reading + _SECONDS_FOR.get(kind, 0)))


def _letter(index: int) -> str:
    return "abcdefghijklmnopqrstuvwxyz"[index]


def _question(
    draft: QuestionDraft, question_id: str, context: LessonContext, problems: list[str], where: str
) -> dict[str, Any] | None:
    form = draft.form.strip().lower().replace("-", "_").replace(" ", "_")
    item: dict[str, Any] = {
        "id": question_id,
        "form": form,
        "concept_id": context.concept_id,
        "stem": tidy(draft.stem),
        "explanation": tidy(draft.explanation),
        "difficulty": min(3, max(1, draft.difficulty)),
        "is_transfer": draft.transfer,
    }
    hint = _text(draft.hint)
    if hint:
        item["hint"] = hint
    if draft.objective is not None and 1 <= draft.objective <= len(context.objectives):
        item["objective_id"] = context.objectives[draft.objective - 1].id

    if form in ("multiple_choice", "prediction"):
        options = _distinct_options(draft.options[:5])
        correct = [index for index, option in enumerate(options) if option.correct]
        if len(correct) != 1:
            problems.append(f'{where}: exactly one option must have "correct": true')
            return None
        item["options"] = []
        for index, option in enumerate(options):
            entry: dict[str, Any] = {"id": _letter(index), "text": tidy(option.text)}
            feedback = _text(option.feedback)
            if feedback:
                entry["feedback"] = feedback
            kind = (option.misconception or "").strip().lower()
            # An unknown label is dropped rather than refused: it is only a hypothesis.
            if kind in MISCONCEPTION_KINDS and not option.correct:
                entry["misconception"] = kind
            item["options"].append(entry)
        item["correct_option"] = _letter(correct[0])
    elif form == "true_false":
        if draft.correct is None:
            problems.append(f'{where}: a true_false question needs "correct": true or false')
            return None
        item["correct"] = draft.correct
    elif form == "numeric":
        if draft.answer is None:
            problems.append(f'{where}: a numeric question needs a number in "answer"')
            return None
        if not _worked_to(draft.explanation, draft.answer, draft.tolerance):
            # The key is not what its own working finds (ADR-049): a learner who works it
            # out right would be told they are wrong. Not a key Adle can trust, or mend.
            problems.append(f"{where}: the answer is not what its explanation works out")
            return None
        item["expected"] = draft.answer
        item["tolerance"] = abs(draft.tolerance) if draft.tolerance is not None else 0.0
        unit = _text(draft.unit)
        if unit:
            item["unit"] = unit
    elif form == "short_answer":
        accepted = [tidy(answer) for answer in draft.accepted if tidy(answer)][:8]
        if not accepted:
            problems.append(f'{where}: a short_answer question needs "accepted" answers')
            return None
        item["accepted"] = accepted
    elif form == "ordering":
        items = [tidy(entry) for entry in draft.items if tidy(entry)][:6]
        item["items"] = [{"id": _letter(index), "text": text} for index, text in enumerate(items)]
    elif form == "explanation":
        rubric = [tidy(point) for point in draft.rubric if tidy(point)][:5]
        item["rubric"] = [
            {"id": f"p{index + 1}", "text": text} for index, text in enumerate(rubric)
        ]
        item["required_points"] = max(1, math.ceil(len(rubric) / 2))
        item["sample_answer"] = tidy(draft.sample_answer or "")
    else:
        problems.append(f'{where}: "{_named(draft.form)}" is not a question form Adle has')
        return None
    return item


#: The title of a part a model left untitled, where what it is names it well enough.
_UNTITLED = {"summary": "Summary", "reflection": "Think it over"}


@dataclass
class LessonCompiler:
    """A lesson's parts turned into the Lesson IR one at a time, as they are written
    (ADR-048), or all at once (``compile_lesson``): a part gets the same ids either way.

    A part is kept only whole. One with a problem is left out and its problems returned,
    and nothing of it is counted: the ids of the parts after it follow from the parts kept.
    """

    context: LessonContext
    segments: list[dict[str, Any]] = field(default_factory=list)
    scenes: list[SceneBrief] = field(default_factory=list)
    figures: list[FigureScene] = field(default_factory=list)
    #: Figures given that could not be drawn as given: their parts are said in words.
    dropped: int = 0
    #: Of the figures, how many are slides (ADR-049).
    slides: int = 0
    questions: int = 0
    #: How many parts have been read, kept or not: a part's place in what was written.
    read: int = 0

    def add(self, segment: SegmentDraft) -> list[str]:
        """Compile the next part as it was written. Its problems, if it has any; then it is
        not kept."""
        index = self.read
        self.read += 1
        if index >= MAX_SEGMENTS:
            return []
        problems: list[str] = []
        where = f"segments.{index}"
        kind = segment.type.strip().lower().replace("-", "_").replace(" ", "_")
        segment_id = f"seg_{index + 1}"
        narration = _narration(segment.beats)
        title = tidy(segment.title)
        if not title:
            # A part left without a title is named by what it is where that says enough
            # (a real model left all three of its checkpoints so, 2026-11-22): not a reason
            # to write the lesson again. Any other part needs its own.
            title = (
                f"Checkpoint {self.questions + 1}"
                if kind == "checkpoint"
                else _UNTITLED.get(kind, "")
            )
            if not title:
                problems.append(f"{where}.title: Field required")
        entry: dict[str, Any] = {
            "id": segment_id,
            "type": kind,
            "title": title,
            "narration": narration,
        }
        asks = 0
        if kind == "checkpoint":
            if segment.question is None:
                return [*problems, f"{where}: a checkpoint needs a question"]
            question = _question(
                segment.question,
                f"q_{self.questions + 1}",
                self.context,
                problems,
                f"{where}.question",
            )
            if question is None:
                return problems
            entry["question"] = question
            asks = 1
        elif kind in ("interaction", "reflection"):
            entry["prompt"] = tidy(segment.prompt or "")
        elif kind == "worked_example":
            entry["problem"] = tidy(segment.problem or "")
        elif kind not in ("explanation", "visualization", "summary"):
            return [
                *problems,
                f'{where}: "{_named(segment.type)}" is not a kind of segment Adle has',
            ]
        if problems:
            return problems

        figure: FigureScene | None = None
        brief: SceneBrief | None = None
        lost = 0
        drawn = None
        scene_id = f"scn_{len(self.scenes) + len(self.figures) + 1}"
        slide = None
        if (
            segment.visual is not None
            and kind in _SLIDE_PARTS
            and self.slides < MAX_SLIDES_PER_LESSON
        ):
            slide = _slide(segment.visual)
            lost = 1 if slide is None else 0
        if slide is not None:
            # The part's picture is a slide, paced by the words it marked (ADR-049).
            compiled_slide, described = slide
            paced = _paced(narration, compiled_slide.steps)
            # Written again with each step no longer than its words (ADR-055).
            fitted = (
                _slide(segment.visual, _step_seconds(paced, compiled_slide.steps))
                if segment.visual is not None
                else None
            )
            if fitted is not None and fitted[0].steps == compiled_slide.steps:
                compiled_slide = fitted[0]
            if kind == "interaction" and not compiled_slide.interactive:
                entry.pop("prompt", None)
                entry["type"] = kind = "visualization"
            # The slide is what this part shows: a board under it would say it twice.
            entry["narration"] = [
                {key: value for key, value in beat.items() if key != "show"} for beat in paced
            ]
            entry["scene"] = {"scene_id": scene_id, "fallback_text": described}
            figure = FigureScene(
                scene_id=scene_id,
                segment_id=segment_id,
                kind="slide",
                title=entry["title"],
                description=described,
                source=compiled_slide.source,
                interactive=compiled_slide.interactive,
            )
        else:
            entry["narration"] = narration = _uncued(narration)
        if (
            slide is None
            and segment.figure is not None
            and kind in _FIGURE_PARTS
            and len(self.figures) - self.slides < MAX_FIGURES_PER_LESSON
        ):
            drawn = _figure(segment.figure, narration)
            if drawn is None:
                lost = 1
            elif kind == "interaction" and not drawn[0].interactive:
                # Nothing to operate: what it shows is still worth watching.
                entry.pop("prompt", None)
                entry["type"] = kind = "visualization"
        if slide is not None:
            pass
        elif drawn is not None:
            compiled_figure, described = drawn
            entry["scene"] = {"scene_id": scene_id, "fallback_text": described}
            figure = FigureScene(
                scene_id=scene_id,
                segment_id=segment_id,
                kind=compiled_figure.kind,
                title=entry["title"],
                description=described,
                source=compiled_figure.source,
                interactive=compiled_figure.interactive,
            )
        else:
            wants_scene = kind in ("visualization", "interaction") or (
                kind in ("explanation", "worked_example") and segment.scene is not None
            )
            if (
                wants_scene
                and segment.scene is not None
                and len(self.scenes) < MAX_SCENES_PER_LESSON
            ):
                description = tidy(segment.scene.description)
                entry["scene"] = {"scene_id": scene_id, "fallback_text": description}
                brief = SceneBrief(
                    scene_id=scene_id,
                    segment_id=segment_id,
                    kind="interactive" if kind == "interaction" else "animation",
                    title=entry["title"],
                    brief=tidy(segment.scene.brief),
                    description=description,
                    narration=[beat["text"] for beat in narration],
                )
            elif kind in ("visualization", "interaction"):
                # No scene was described, or the lesson already has as many as it may ask
                # for: the part is still worth having as words.
                described = tidy(segment.scene.description) if segment.scene else None
                entry = _as_explanation(entry, described)

        entry = _shown_somewhere(entry, segment)
        entry["estimated_seconds"] = _seconds(entry["type"], entry["narration"])
        self.segments.append(entry)
        self.questions += asks
        self.dropped += lost
        if figure is not None:
            self.figures.append(figure)
            self.slides += 1 if slide is not None else 0
        if brief is not None:
            self.scenes.append(brief)
        return []

    def lesson(
        self,
        header: LessonHeaderDraft,
        practice: Sequence[QuestionDraft] = (),
        voice: str | None = None,
    ) -> dict[str, Any]:
        """The lesson in IR form, not yet validated, with the parts kept so far."""
        context = self.context
        strategy = header.strategy.strip().lower().replace("-", "_").replace(" ", "_")
        if context.strategy in STRATEGIES:
            strategy = context.strategy
        cited: dict[str, PassageRef] = {}
        for number in header.sources:
            # Only passages that were actually supplied can be cited.
            if 1 <= number <= len(context.passages):
                passage = context.passages[number - 1]
                cited.setdefault(passage.section_id, passage)
        lesson: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "lesson_id": context.lesson_id,
            "course_id": context.course_id,
            "title": tidy(header.title),
            "concept_ids": [context.concept_id],
            "objectives": [
                {"objective_id": objective.id, "statement": objective.statement}
                for objective in context.objectives[:6]
            ],
            "source_refs": [
                {
                    "source_id": passage.source_id,
                    "section_id": passage.section_id,
                    "source_name": passage.source_name,
                    "locator": passage.locator,
                }
                for passage in list(cited.values())[:12]
            ],
            "grounding": "materials" if cited else "general_knowledge",
            "strategy": strategy if strategy in STRATEGIES else "visual",
            "estimated_minutes": minutes_for(self.segments),
            "segments": list(self.segments),
            "practice": compile_practice(practice, context),
        }
        spoken_as = voice_description(voice)
        if spoken_as is not None:
            lesson["voice"] = spoken_as
        return lesson


#: A number as a question's working writes it: 0.25, 3/13, $\frac{3}{13}$, 25%, 1,200.
_FRACTION = re.compile(
    r"\\[dt]?frac\{\s*(-?[\d.,]+)\s*\}\{\s*(-?[\d.,]+)\s*\}|(-?[\d.,]*\d)\s*/\s*(-?[\d.,]*\d)"
)
_DECIMAL = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?|(?<![\w.])-?\.\d+%?")


def _figure_of(text: str) -> float | None:
    """The one value a short text says, when it says one (an option such as "12/52",
    "$\\frac{3}{13}$", "0.25" or "25%"); None for anything else."""
    plain = " ".join(text.replace("$", " ").split())
    whole = _FRACTION.fullmatch(plain)
    if whole:
        top, bottom = (
            (whole.group(1), whole.group(2)) if whole.group(1) else (whole.group(3), whole.group(4))
        )
        try:
            denominator = float(bottom.replace(",", ""))
            return float(top.replace(",", "")) / denominator if denominator else None
        except ValueError:
            return None
    single = _DECIMAL.fullmatch(plain)
    if single:
        figure = single.group(0)
        try:
            value = float(figure.rstrip("%").replace(",", ""))
        except ValueError:
            return None
        return value / 100 if figure.endswith("%") else value
    return None


def _distinct_options(options: Sequence[OptionDraft]) -> list[OptionDraft]:
    """The options without a wrong one that is the right one written another way ("12/52"
    beside "3/13", as a real lesson asked without thinking, 2026-11-22): a learner who
    chose it would be told they were wrong (ADR-049)."""
    right = [_figure_of(option.text) for option in options if option.correct]
    if len(right) != 1 or right[0] is None:
        return list(options)
    value = right[0]
    kept = [
        option
        for option in options
        if option.correct
        or (figure := _figure_of(option.text)) is None
        or abs(figure - value) > 1e-9 * max(1.0, abs(value))
    ]
    return kept if len(kept) >= 2 else list(options)


def _figures_in(text: str) -> list[float]:
    """Every value a question's working writes: its numbers, and its fractions worked out."""
    plain = text.replace("$", " ")
    found: list[float] = []
    for match in _FRACTION.finditer(plain):
        figure = _figure_of(match.group(0))
        if figure is not None:
            found.append(figure)
    for match in _DECIMAL.finditer(plain):
        figure = _figure_of(match.group(0))
        if figure is not None:
            found.append(figure)
    return found


def _worked_to(explanation: str, answer: float, tolerance: float | None) -> bool:
    """Whether a numeric question's explanation arrives at its key: some value it writes is
    the key, to within the tolerance, or to the places the key is given to. An explanation
    that writes no number at all says nothing either way, and is let be."""
    figures = _figures_in(explanation)
    if not figures:
        return True
    places = len(f"{answer:.10g}".partition(".")[2])
    allowed = max(abs(tolerance or 0.0), 0.5 * 10.0 ** (-places), 1e-9 * max(1.0, abs(answer)))
    return any(abs(figure - answer) <= allowed + 1e-12 for figure in figures)


def compile_practice(
    drafts: Sequence[QuestionDraft], context: LessonContext
) -> list[dict[str, Any]]:
    """The questions kept for practice. Extra questions are a bonus: one that cannot be used
    is left out, and is never a reason to write the lesson again."""
    practice: list[dict[str, Any]] = []
    for index, extra in enumerate(drafts[:MAX_PRACTICE_ITEMS], start=1):
        item = _question(extra, f"q_practice_{index}", context, [], f"practice.{index - 1}")
        if item is not None and _is_usable(item):
            practice.append(item)
    return practice


def compile_lesson(draft: LessonDraft, context: LessonContext) -> CompiledLesson:
    """Turn a whole draft into an (unvalidated) lesson in IR form, plus the scenes still to
    be written.

    Raises ``DraftError`` for problems only a rewrite can fix. Everything else is
    left to ``parse_bundle``, which reports precisely.
    """
    compiler = LessonCompiler(context)
    problems: list[str] = []
    for segment in draft.segments:
        problems += compiler.add(segment)
    if problems:
        raise DraftError(problems[:12])
    return CompiledLesson(
        lesson=compiler.lesson(draft, draft.practice, draft.voice),
        scenes=compiler.scenes,
        figures=compiler.figures,
        figures_dropped=compiler.dropped,
    )


_LONG_DISPLAY = TypeAdapter(LongDisplay)


def _slide(raw: dict[str, Any], seconds: list[float] | None = None) -> Any:
    """A part's slide, drawn, with its description in words (the model's, or Adle's from
    the script); None when nothing of it can be drawn. A slide is never a reason to write
    the lesson again: its part is said in words instead."""
    try:
        drawn = compile_slide(raw, seconds)
    except SlideError:
        return None
    if drawn.left_out:
        # What was left out is not logged in words: a script's text is the model's.
        logger.info("generation.slide_parts_left_out count=%s", len(drawn.left_out))
    for candidate in (raw.get("description"), drawn.described, "A picture of this part."):
        try:
            described = _LONG_DISPLAY.validate_python(tidy(str(candidate or "")))
        except ValidationError:
            continue
        if described:
            return drawn, described
    return None


def _figure(raw: dict[str, Any], narration: list[dict[str, Any]]) -> Any:
    """A part's figure, drawn, with its description in words (the model's, or Adle's from
    the figure's data); None when it cannot be drawn as given. A figure is never a reason
    to write the lesson again: its part is said in words instead."""
    try:
        drawn = compile_figure(raw, beat_seconds=beat_seconds([beat["text"] for beat in narration]))
    except FigureError:
        return None
    try:
        if drawn.mended:
            # Drawn otherwise than the model wrote it: its words describe what is not shown.
            raise ValidationError.from_exception_data("mended", [])
        described = _LONG_DISPLAY.validate_python(tidy(str(raw.get("description") or "")))
    except ValidationError:
        # The model said nothing usable of it (nothing at all, or a link): Adle says what
        # it shows, from its data, so that it is never a picture without words.
        try:
            described = _LONG_DISPLAY.validate_python(drawn.described)
        except ValidationError:
            return None
    return drawn, described


#: The longest description of a voice that is kept, as the lesson format allows.
_VOICE_CHARACTERS = 240


def voice_description(text: str | None) -> str | None:
    """What the model said of the narrator's voice, as one plain sentence, or nothing.

    It is only ever a description for a speech model to design a voice from. Anything a
    lesson could not hold (a symbol of mathematics, a link, markup) loses the voice, never
    the lesson."""
    if not text:
        return None
    plain = " ".join(tidy(text).replace("$", " ").replace("\\", " ").split())
    if len(plain) > _VOICE_CHARACTERS:
        plain = plain[: _VOICE_CHARACTERS - 1].rsplit(" ", 1)[0].rstrip(",;:") + "."
    try:
        _VOICE.validate_python(plain)
    except ValidationError:
        return None
    return plain or None


_QUESTION = TypeAdapter(AssessmentItem)
_VOICE = TypeAdapter(VoiceDescription)


def _is_usable(item: dict[str, Any]) -> bool:
    """Whether a compiled question would be accepted as part of a lesson."""
    try:
        _QUESTION.validate_python(item)
    except ValidationError:
        return False
    return True


def _shown_somewhere(entry: dict[str, Any], segment: SegmentDraft) -> dict[str, Any]:
    """A worked example or a summary shows what it says: on the board, or in its picture.
    Written without either (its slide could not be drawn, and the board is no longer asked
    for, ADR-049), its first line puts the picture's description, or its title, on the
    board. A worked example without a problem to solve is an explanation (ADR-047)."""
    if entry["type"] == "worked_example" and not entry.get("problem"):
        entry = {key: value for key, value in entry.items() if key != "problem"}
        entry["type"] = "explanation"
    if entry["type"] not in ("worked_example", "summary") or "scene" in entry:
        return entry
    narration = [dict(beat) for beat in entry["narration"]]
    if not narration or any(beat.get("show") for beat in narration):
        return entry
    raw = segment.visual.get("description") if isinstance(segment.visual, dict) else None
    for candidate in (raw, entry["title"]):
        shown = _text(str(candidate)) if candidate else None
        if shown and shown.count("$") % 2 == 0 and len(shown) <= MAX_BOARD_CHARACTERS:
            narration[0]["show"] = shown
            return {**entry, "narration": narration}
    return entry


def _as_explanation(segment: dict[str, Any], described: str | None) -> dict[str, Any]:
    """The same part without its scene: narration, with the picture's description on the board."""
    narration = [dict(beat) for beat in segment.get("narration", [])]
    nothing_shown = not any(beat.get("show") for beat in narration)
    if narration and described and len(described) <= 600 and nothing_shown:
        narration[0]["show"] = described
    return {
        "id": segment["id"],
        "type": "explanation",
        "title": segment["title"],
        "narration": narration,
        "estimated_seconds": _seconds("explanation", narration),
    }


def without_scene(lesson: dict[str, Any], scene_id: str) -> dict[str, Any]:
    """The lesson with one scene taken out, for when that scene could not be made.

    A visualization or an interaction becomes an explanation that carries the
    scene's description; any other part simply loses its picture.
    """
    segments = []
    for segment in lesson["segments"]:
        scene = segment.get("scene")
        if not scene or scene.get("scene_id") != scene_id:
            segments.append(segment)
        elif segment["type"] in ("visualization", "interaction"):
            segments.append(_as_explanation(segment, scene.get("fallback_text")))
        else:
            segments.append({key: value for key, value in segment.items() if key != "scene"})
    return {**lesson, "segments": segments}


def as_visualization(lesson: dict[str, Any], scene_id: str) -> dict[str, Any]:
    """An interaction whose scene turned out to have nothing to operate becomes a visualization."""
    segments = []
    for segment in lesson["segments"]:
        scene = segment.get("scene")
        if scene and scene.get("scene_id") == scene_id and segment["type"] == "interaction":
            changed = {key: value for key, value in segment.items() if key != "prompt"}
            changed["type"] = "visualization"
            changed["estimated_seconds"] = _seconds("visualization", changed["narration"])
            segments.append(changed)
        else:
            segments.append(segment)
    return {**lesson, "segments": segments}


# -- the curriculum draft -------------------------------------------------------


class ConceptDraft(_Draft):
    title: str = Field(min_length=1)
    summary: str = ""
    objectives: list[str] = Field(default_factory=list)
    #: Numbers of earlier concepts in this list (counted from 1) that must come first.
    needs: list[int] = Field(default_factory=list)
    #: One reason per entry of ``needs``, in the same order.
    reasons: list[str] = Field(default_factory=list)
    #: Numbers of the supplied headings this concept is drawn from.
    sources: list[int] = Field(default_factory=list)


class CurriculumDraft(_Draft):
    concepts: list[ConceptDraft] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class ProposedNeed:
    #: Index into the proposal's own list of concepts.
    index: int
    reason: str


@dataclass(frozen=True, slots=True)
class ProposedConcept:
    title: str
    summary: str
    objectives: list[str]
    needs: list[ProposedNeed]
    section_ids: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "objectives": self.objectives,
            "needs": [{"index": need.index, "reason": need.reason} for need in self.needs],
            "section_ids": self.section_ids,
        }


def _named(value: str) -> str:
    """A model's own word for something, made fit to be quoted back to it.

    What is wrong with a draft is put into the request for a second one. The name of a kind
    is meant to be one word; whatever came in its place is cut to a few characters of plain
    text, so that a draft cannot write its own instructions into the next request.
    """
    plain = "".join(
        character if character.isalnum() or character in "_-" else " " for character in value
    )
    return " ".join(plain.split())[:32].strip() or "that"


def _clip(text: str, limit: int) -> str:
    """Shorten at a word boundary. Used for titles and summaries, never for lesson content."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") or text[:limit]


def compile_curriculum(
    data: dict[str, Any], *, existing_titles: list[str], section_ids: list[str]
) -> list[ProposedConcept]:
    """Turn a model's proposal into concepts that can be offered to the learner.

    A concept may only need concepts listed before it, so the proposal cannot
    contain a loop. Concepts the course already has are left out, and so are
    references to them.
    """
    try:
        draft = CurriculumDraft.model_validate(data)
    except ValidationError as error:
        raise DraftError(_problems(error)) from error

    taken = {" ".join(title.split()).casefold() for title in existing_titles}
    #: Position in the draft -> position in what is kept.
    kept: dict[int, int] = {}
    proposed: list[ProposedConcept] = []
    for position, concept in enumerate(draft.concepts):
        if len(proposed) >= MAX_PROPOSED_CONCEPTS:
            break
        title = _clip(tidy(concept.title), 120)
        if not title or title.casefold() in taken:
            continue
        taken.add(title.casefold())
        needs: dict[int, ProposedNeed] = {}
        for order, number in enumerate(concept.needs):
            earlier = number - 1
            if earlier in kept and earlier < position:
                reason = tidy(concept.reasons[order]) if order < len(concept.reasons) else ""
                needs.setdefault(
                    kept[earlier], ProposedNeed(index=kept[earlier], reason=_clip(reason, 300))
                )
        sections: dict[str, None] = {}
        for number in concept.sources:
            if 1 <= number <= len(section_ids):
                sections.setdefault(section_ids[number - 1])
        objectives = [
            _clip(tidy(statement), 300) for statement in concept.objectives if tidy(statement)
        ][:MAX_PROPOSED_OBJECTIVES]
        kept[position] = len(proposed)
        proposed.append(
            ProposedConcept(
                title=title,
                summary=_clip(tidy(concept.summary), 600),
                objectives=objectives,
                needs=list(needs.values())[:6],
                section_ids=list(sections)[:6],
            )
        )
    if not proposed:
        raise DraftError(
            ["The proposal contains no concept that the course does not already have."]
        )
    return proposed


# -- an answer to a question the learner asked ------------------------------------------

MAX_ANSWER_PARAGRAPHS = 4
MAX_ANSWER_CITATIONS = 3


class AnswerDraft(_Draft):
    paragraphs: list[str] = Field(min_length=1)
    #: Numbers of the supplied excerpts the answer draws on.
    sources: list[int] = Field(default_factory=list)


class _Answer(BaseModel):
    """An answer as it is kept: text to read, a few short paragraphs of it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paragraphs: list[Display] = Field(min_length=1, max_length=MAX_ANSWER_PARAGRAPHS)


@dataclass(frozen=True, slots=True)
class CompiledAnswer:
    paragraphs: list[str]
    #: The passages the answer says it used, of those it was shown.
    citations: list[PassageRef]


_BLANK_LINE = re.compile(r"\n\s*\n")


def compile_answer(text: str, passages: Sequence[PassageRef] = ()) -> CompiledAnswer:
    """Read a model's answer to a learner's question.

    It was asked for a JSON object. A model that answers in plain sentences has still
    answered, so those are taken as the answer: there is no structure in it to get
    wrong. Either way the text is display text like any other (no links, no markup),
    and a source is a number the prompt offered or it is dropped.
    """
    stripped = text.strip()
    numbers: list[int] = []
    if "{" in stripped and '"paragraphs"' in stripped:
        try:
            draft = AnswerDraft.model_validate(extract_json_object(stripped))
        except ValidationError as error:
            raise DraftError(_problems(error)) from error
        raw, numbers = draft.paragraphs, draft.sources
    elif stripped.startswith(("{", "[", "```")):
        raise DraftError(
            ['The answer must be one JSON object with a "paragraphs" list and nothing else.']
        )
    else:
        raw = _BLANK_LINE.split(stripped)
    cleaned = [paragraph for paragraph in (tidy(part) for part in raw) if paragraph]
    try:
        answer = _Answer.model_validate({"paragraphs": cleaned})
    except ValidationError as error:
        raise DraftError(_problems(error)) from error
    cited: dict[int, PassageRef] = {}
    for number in numbers:
        if 1 <= number <= len(passages):
            cited.setdefault(number, passages[number - 1])
    return CompiledAnswer(
        paragraphs=list(answer.paragraphs),
        citations=list(cited.values())[:MAX_ANSWER_CITATIONS],
    )
