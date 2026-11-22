"""The Lesson IR: the one contract between generation, storage, and the player.

A lesson is data, never code or markup. It names what is said, what is shown,
which scene plays, and what is asked; the player decides how each of those
looks. Anything a model writes must fit this shape exactly before it is stored
(PLAN.md 9): unknown fields are rejected, every text is bounded and free of
links, paths, and markup, and every reference must resolve.

Two kinds of text
-----------------
*Spoken* text is narration. It is read aloud and shown as a caption, so it is
plain words: mathematics is said ("w times x plus b"), not typeset.

*Display* text is read on screen: titles, question stems, worked steps. It may
contain inline mathematics between dollar signs (``$w \\cdot x + b$``), which
the player typesets. Nothing else in it is interpreted.

Scenes are stored beside the lesson as complete Python files and referred to by
id. A lesson that refers to a scene always carries the same idea in words
(``fallback_text``), so it survives a scene that cannot run.
"""

from __future__ import annotations

import math
import re
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

SCHEMA_VERSION = "1.0"

MAX_SEGMENTS = 14
MAX_BEATS = 12
MAX_PRACTICE_ITEMS = 8
MAX_SCENE_SOURCE_CHARACTERS = 40_000

QUESTION_FORMS = (
    "multiple_choice",
    "true_false",
    "numeric",
    "short_answer",
    "ordering",
    "prediction",
    "explanation",
)
MISCONCEPTION_KINDS = (
    "prerequisite_gap",
    "definition_confusion",
    "notation_confusion",
    "procedure_order",
    "causal_confusion",
    "arithmetic_slip",
    "misread_question",
    "overgeneralization",
)
STRATEGIES = (
    "visual",
    "worked_example",
    "analogy",
    "mathematical",
    "socratic",
    "computational",
)

# -- text that is safe to show ------------------------------------------------

# These patterns are deliberately narrow. Lesson prose says things like "this data: 2, 4, 6"
# and "if x < a and y > 3", and display text carries TeX such as "f:\mathbb{R}", none of
# which may be mistaken for a link, a tag, or a path.
_LINK = re.compile(
    r"(?i)\b(?:https?|ftp|file)://"
    r"|\b(?:javascript|vbscript)\s*:"
    r"|\bdata:[a-z]+/[a-z0-9.+-]+"
    r"|\bwww\.[a-z0-9-]+\.[a-z]"
)
_MARKUP = re.compile(
    r"(?i)<\s*/?\s*(?:script|iframe|img|svg|object|embed|link|style|form|input|button|video|"
    r"audio|base|meta|html|body|div|span)\b"
    r"|<\s*a\s+href"
    r"|<\s*/?\s*(?:p|br|h[1-6])\s*/?\s*>"
)
_PATH = re.compile(
    r"\b[A-Z]:\\[A-Za-z0-9_ .-]+\\" r"|(?:^|\s)(?:/etc/|/usr/|/bin/|/home/|/var/|~/|\.\./)"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _safe(text: str) -> str:
    """Refuse text that carries a link, markup, a file path, or control characters.

    The player shows text as text, so none of these could do anything; refusing
    them keeps lessons clean and catches a model that has gone off the rails.
    """
    if _CONTROL.search(text):
        raise ValueError("contains control characters")
    if _LINK.search(text):
        raise ValueError("contains a link; lessons cannot refer to addresses")
    if _MARKUP.search(text):
        raise ValueError("contains markup; lessons are plain text")
    if _PATH.search(text):
        raise ValueError("contains a file path")
    return text


def _spoken(text: str) -> str:
    _safe(text)
    if "$" in text or "\\" in text:
        raise ValueError("narration is read aloud: write mathematics in words, not notation")
    return text


def _display(text: str) -> str:
    _safe(text)
    if text.count("$") % 2:
        raise ValueError("inline mathematics must be closed with a second dollar sign")
    return text


Spoken = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=700),
    AfterValidator(_spoken),
]
Display = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=600),
    AfterValidator(_display),
]
ShortDisplay = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(_display),
]
LongDisplay = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1400),
    AfterValidator(_display),
]

#: How a lesson's narrator sounds, in a sentence: what a voice is designed from (ADR-042).
VoiceDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
    AfterValidator(_spoken),
]

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z]{2,5}_[0-9a-f]{20}$")]
#: Ids that only need to be unique inside one lesson, chosen by whoever writes it.
SegmentId = Annotated[str, StringConstraints(pattern=r"^seg_[a-z0-9_]{1,40}$")]
ItemId = Annotated[str, StringConstraints(pattern=r"^q_[a-z0-9_]{1,40}$")]
OptionId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,15}$")]
SceneId = Annotated[str, StringConstraints(pattern=r"^scn_[a-z0-9_]{1,40}$")]

QuestionForm = Literal[
    "multiple_choice",
    "true_false",
    "numeric",
    "short_answer",
    "ordering",
    "prediction",
    "explanation",
]
MisconceptionKind = Literal[
    "prerequisite_gap",
    "definition_confusion",
    "notation_confusion",
    "procedure_order",
    "causal_confusion",
    "arithmetic_slip",
    "misread_question",
    "overgeneralization",
]
Strategy = Literal[
    "visual", "worked_example", "analogy", "mathematical", "socratic", "computational"
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# -- provenance ---------------------------------------------------------------


class SourceCitation(_Strict):
    """A place in the learner's materials that the lesson draws on."""

    source_id: Identifier
    section_id: Identifier
    source_name: ShortDisplay
    #: "page 3" or a heading path, as the learner would recognise it.
    locator: ShortDisplay


# -- what is said and shown ---------------------------------------------------


class Beat(_Strict):
    """One breath of narration, and what appears on screen as it starts."""

    text: Spoken
    #: Shown on the lesson's board when this beat begins: a key point or a worked step.
    show: Display | None = None
    #: Move the scene on to its animation when this beat begins (see ``SceneRef``).
    advance_scene: bool = False


class SceneRef(_Strict):
    #: Refers to a ``SceneArtifact`` in the same bundle.
    scene_id: SceneId
    #: The same idea in words. Shown when the scene cannot run and always
    #: available as its text alternative.
    fallback_text: LongDisplay


# -- questions ----------------------------------------------------------------


class _Item(_Strict):
    id: ItemId
    #: The concept this question gives evidence about.
    concept_id: Identifier
    objective_id: Identifier | None = None
    stem: Display
    #: Shown after answering, whatever the answer: why the right answer is right.
    explanation: LongDisplay
    #: Offered on request. Using it makes a correct answer count for less.
    hint: Display | None = None
    difficulty: int = Field(default=2, ge=1, le=3)
    #: Applies the idea to a situation the lesson did not show.
    is_transfer: bool = False


class Option(_Strict):
    id: OptionId
    text: ShortDisplay
    #: Shown when this option is chosen: what it gets right or wrong.
    feedback: Display | None = None
    #: The kind of mistake choosing this option suggests. A hypothesis, not a diagnosis.
    misconception: MisconceptionKind | None = None


class ChoiceItem(_Item):
    """Choose one. ``prediction`` is the same shape, asked before the lesson shows the answer."""

    form: Literal["multiple_choice", "prediction"]
    options: list[Option] = Field(min_length=2, max_length=5)
    correct_option: OptionId

    @model_validator(mode="after")
    def _options_are_coherent(self) -> ChoiceItem:
        ids = [option.id for option in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError("option ids must be different")
        if self.correct_option not in ids:
            raise ValueError("correct_option must be one of the options")
        texts = [option.text.casefold() for option in self.options]
        if len(set(texts)) != len(texts):
            raise ValueError("two options say the same thing")
        return self


class TrueFalseItem(_Item):
    form: Literal["true_false"]
    correct: bool


class NumericItem(_Item):
    form: Literal["numeric"]
    expected: float
    #: Answers within this distance of ``expected`` are correct.
    tolerance: float = Field(default=0.0, ge=0.0)
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None

    @model_validator(mode="after")
    def _numbers_are_finite(self) -> NumericItem:
        if not (math.isfinite(self.expected) and math.isfinite(self.tolerance)):
            raise ValueError("expected and tolerance must be finite numbers")
        return self


class ShortAnswerItem(_Item):
    """A word or short phrase, matched against accepted answers after normalising."""

    form: Literal["short_answer"]
    accepted: list[ShortDisplay] = Field(min_length=1, max_length=8)


class OrderingItem(_Item):
    """Put the items in order. They are listed here in the correct order."""

    form: Literal["ordering"]
    items: list[Option] = Field(min_length=3, max_length=6)

    @model_validator(mode="after")
    def _items_are_distinct(self) -> OrderingItem:
        ids = [item.id for item in self.items]
        texts = [item.text.casefold() for item in self.items]
        if len(set(ids)) != len(ids) or len(set(texts)) != len(texts):
            raise ValueError("ordering items must be different from each other")
        return self


class RubricPoint(_Strict):
    id: OptionId
    #: One thing a good answer says.
    text: Display


class ExplanationItem(_Item):
    """Explain in your own words. Judged against a rubric, never by exact wording."""

    form: Literal["explanation"]
    rubric: list[RubricPoint] = Field(min_length=1, max_length=5)
    #: How many rubric points a correct answer covers.
    required_points: int = Field(default=1, ge=1, le=5)
    sample_answer: LongDisplay

    @model_validator(mode="after")
    def _rubric_is_coherent(self) -> ExplanationItem:
        ids = [point.id for point in self.rubric]
        if len(set(ids)) != len(ids):
            raise ValueError("rubric point ids must be different")
        if self.required_points > len(self.rubric):
            raise ValueError("required_points cannot exceed the number of rubric points")
        return self


AssessmentItem = Annotated[
    ChoiceItem | TrueFalseItem | NumericItem | ShortAnswerItem | OrderingItem | ExplanationItem,
    Field(discriminator="form"),
]


def guess_probability(item: AssessmentItem) -> float:
    """How likely a correct answer is from someone who does not have the concept."""
    if isinstance(item, ChoiceItem):
        return 1.0 / len(item.options)
    if isinstance(item, TrueFalseItem):
        return 0.5
    if isinstance(item, OrderingItem):
        return 1.0 / math.factorial(len(item.items))
    if isinstance(item, ExplanationItem):
        return 0.05
    return 0.02


# -- segments -----------------------------------------------------------------


class _Segment(_Strict):
    id: SegmentId
    title: ShortDisplay
    estimated_seconds: int = Field(ge=5, le=900)
    narration: list[Beat] = Field(default_factory=list, max_length=MAX_BEATS)


class ExplanationSegment(_Segment):
    """Narration with key points on the board, and optionally a scene beside it."""

    type: Literal["explanation"]
    narration: list[Beat] = Field(min_length=1, max_length=MAX_BEATS)
    scene: SceneRef | None = None


class VisualizationSegment(_Segment):
    """An animation, narrated."""

    type: Literal["visualization"]
    narration: list[Beat] = Field(min_length=1, max_length=MAX_BEATS)
    scene: SceneRef


class InteractionSegment(_Segment):
    """A scene the learner manipulates. Understandable without touching it."""

    type: Literal["interaction"]
    scene: SceneRef
    #: What to try, and what to look for.
    prompt: Display


class CheckpointSegment(_Segment):
    """A question. The lesson waits until it is answered or explicitly skipped."""

    type: Literal["checkpoint"]
    question: AssessmentItem


class WorkedExampleSegment(_Segment):
    """A problem solved step by step: each beat says a step and shows it."""

    type: Literal["worked_example"]
    problem: Display
    narration: list[Beat] = Field(min_length=1, max_length=MAX_BEATS)
    scene: SceneRef | None = None

    @model_validator(mode="after")
    def _steps_are_shown(self) -> WorkedExampleSegment:
        if not any(beat.show for beat in self.narration):
            raise ValueError("a worked example must show at least one step")
        return self


class ReflectionSegment(_Segment):
    """A question to think about. Not scored; the learner may write a note or move on."""

    type: Literal["reflection"]
    prompt: Display


class SummarySegment(_Segment):
    type: Literal["summary"]
    narration: list[Beat] = Field(min_length=1, max_length=MAX_BEATS)

    @model_validator(mode="after")
    def _points_are_shown(self) -> SummarySegment:
        if not any(beat.show for beat in self.narration):
            raise ValueError("a summary must show at least one key point")
        return self


Segment = Annotated[
    ExplanationSegment
    | VisualizationSegment
    | InteractionSegment
    | CheckpointSegment
    | WorkedExampleSegment
    | ReflectionSegment
    | SummarySegment,
    Field(discriminator="type"),
]


# -- the lesson ---------------------------------------------------------------


class LessonObjective(_Strict):
    #: The curriculum objective this restates, when there is one.
    objective_id: Identifier | None = None
    statement: Display


class Lesson(_Strict):
    schema_version: Literal["1.0"]
    lesson_id: Identifier
    course_id: Identifier
    title: ShortDisplay
    concept_ids: list[Identifier] = Field(min_length=1, max_length=3)
    objectives: list[LessonObjective] = Field(min_length=1, max_length=6)
    source_refs: list[SourceCitation] = Field(default_factory=list, max_length=12)
    #: Where the content comes from. The player says so; "materials" needs citations.
    grounding: Literal["materials", "general_knowledge", "sample"]
    strategy: Strategy
    estimated_minutes: int = Field(ge=1, le=60)
    segments: list[Segment] = Field(min_length=1, max_length=MAX_SEGMENTS)
    #: Questions that are not part of the lesson's flow. They are asked when the learner
    #: practises or reviews, so that a review is more than the lesson's questions again.
    practice: list[AssessmentItem] = Field(default_factory=list, max_length=MAX_PRACTICE_ITEMS)
    #: How the narrator sounds, written with the lesson, for the voice that is designed for
    #: it when the Expressive voice reads it (ADR-042). The voice only: never what it says.
    voice: VoiceDescription | None = None

    @model_validator(mode="after")
    def _is_coherent(self) -> Lesson:
        if len(set(self.concept_ids)) != len(self.concept_ids):
            raise ValueError("concept_ids must be different")
        segment_ids = [segment.id for segment in self.segments]
        if len(set(segment_ids)) != len(segment_ids):
            raise ValueError("segment ids must be different")
        questions = self.all_questions()
        question_ids = [question.id for question in questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("question ids must be different")
        for question in questions:
            if question.concept_id not in self.concept_ids:
                raise ValueError(
                    f"question {question.id} is about a concept this lesson does not teach"
                )
        if self.grounding == "materials" and not self.source_refs:
            raise ValueError("a lesson grounded in the learner's materials must cite them")
        if sum(segment.estimated_seconds for segment in self.segments) > 60 * 60:
            raise ValueError("a lesson cannot be longer than an hour")
        return self

    def scene_ids(self) -> list[str]:
        """Every scene the lesson refers to, in order, once."""
        seen: dict[str, None] = {}
        for segment in self.segments:
            scene = getattr(segment, "scene", None)
            if isinstance(scene, SceneRef):
                seen.setdefault(scene.scene_id)
        return list(seen)

    def questions(self) -> list[AssessmentItem]:
        """The questions asked in the course of the lesson, in order."""
        return [
            segment.question for segment in self.segments if isinstance(segment, CheckpointSegment)
        ]

    def all_questions(self) -> list[AssessmentItem]:
        """Every question the lesson carries: those in its flow, then those kept for practice."""
        return [*self.questions(), *self.practice]


# -- scenes and the bundle ----------------------------------------------------


class SceneArtifact(_Strict):
    """One complete Wanim scene file, with what the static policy found in it."""

    id: SceneId
    #: Why the scene exists: what the learner should see or do.
    purpose: Display
    #: The whole Python file. Never a fragment or a patch.
    source: Annotated[str, StringConstraints(min_length=1, max_length=MAX_SCENE_SOURCE_CHARACTERS)]
    # -- filled in from the source by ``bundle.inspect_scene``; never taken on trust --
    content_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    wanim_version: Annotated[str, StringConstraints(min_length=1, max_length=20)]
    scene_class: Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")]
    interactive: bool
    controls: list[Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,31}$")]] = Field(
        default_factory=list, max_length=16
    )
    events: list[Literal["passed", "explored", "progress"]] = Field(
        default_factory=list, max_length=3
    )


class LessonBundle(_Strict):
    """A lesson and the scenes it plays: what is stored and what the player loads."""

    lesson: Lesson
    scenes: list[SceneArtifact] = Field(default_factory=list, max_length=MAX_SEGMENTS)
    #: Scenes that parts refer to and that are still being drawn (ADR-031). The lesson is
    #: whole without them: every part with a picture carries its description in words.
    pending_scene_ids: list[SceneId] = Field(default_factory=list, max_length=MAX_SEGMENTS)

    @model_validator(mode="after")
    def _scenes_resolve(self) -> LessonBundle:
        available = {scene.id: scene for scene in self.scenes}
        if len(available) != len(self.scenes):
            raise ValueError("scene ids must be different")
        coming = set(self.pending_scene_ids)
        if len(coming) != len(self.pending_scene_ids):
            raise ValueError("a scene still to come is listed more than once")
        if coming & set(available):
            raise ValueError("a scene is both included and still to come")
        for segment in self.lesson.segments:
            scene_ref = getattr(segment, "scene", None)
            if not isinstance(scene_ref, SceneRef):
                continue
            if scene_ref.scene_id in coming:
                # Whether it turns out to have something to operate is known when it arrives.
                continue
            scene = available.get(scene_ref.scene_id)
            if scene is None:
                raise ValueError(f"segment {segment.id} refers to a scene that is not included")
            if isinstance(segment, InteractionSegment) and not scene.interactive:
                raise ValueError(
                    f"segment {segment.id} is an interaction "
                    "but its scene has nothing to interact with"
                )
        used = set(self.lesson.scene_ids())
        if set(available) - used:
            raise ValueError("a scene is included that no segment uses")
        if coming - used:
            raise ValueError("a scene is awaited that no segment uses")
        return self
