"""What the lesson player is given: the lesson, without the answers.

Scoring happens in the core (``evaluation.scoring``). The interface therefore
never needs to know which option is right, what number is expected, or which
answers are accepted, and it is not sent them: they cannot leak into the page,
the accessibility tree, or a screenshot. Options and items to order arrive in a
shuffled order that is stable for a given lesson, so nothing can be read from
position and a reload does not reshuffle.
"""

from __future__ import annotations

import hashlib
import hmac
import random
from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from adle_core.lessons.ir import (
    AssessmentItem,
    CheckpointSegment,
    ChoiceItem,
    Display,
    ExplanationItem,
    ExplanationSegment,
    Identifier,
    InteractionSegment,
    ItemId,
    Lesson,
    LessonObjective,
    LongDisplay,
    NumericItem,
    OptionId,
    OrderingItem,
    QuestionForm,
    ReflectionSegment,
    ShortDisplay,
    SourceCitation,
    Strategy,
    SummarySegment,
    VisualizationSegment,
    WorkedExampleSegment,
    _Segment,
    _Strict,
)


class PlayerOption(_Strict):
    id: OptionId
    text: ShortDisplay


class PlayerRubricPoint(_Strict):
    id: OptionId
    text: Display


class PlayerQuestion(_Strict):
    """A question as the learner sees it before answering."""

    id: ItemId
    form: QuestionForm
    concept_id: Identifier
    stem: Display
    hint: Display | None = None
    difficulty: int
    is_transfer: bool
    #: Choices, or the items to put in order. Shuffled.
    options: list[PlayerOption] = Field(default_factory=list)
    #: The unit a numeric answer is expected in, if any.
    unit: Annotated[str, StringConstraints(max_length=20)] | None = None
    #: For "explain in your own words": shown once the learner has written an
    #: answer, so they can compare it. Marking against it is self-assessment.
    rubric: list[PlayerRubricPoint] = Field(default_factory=list)
    sample_answer: LongDisplay | None = None


class PlayerCheckpointSegment(_Segment):
    type: Literal["checkpoint"]
    question: PlayerQuestion


PlayerSegment = Annotated[
    ExplanationSegment
    | VisualizationSegment
    | InteractionSegment
    | PlayerCheckpointSegment
    | WorkedExampleSegment
    | ReflectionSegment
    | SummarySegment,
    Field(discriminator="type"),
]


class PlayerLesson(_Strict):
    schema_version: Literal["1.0"]
    lesson_id: Identifier
    course_id: Identifier
    title: ShortDisplay
    concept_ids: list[Identifier]
    objectives: list[LessonObjective]
    source_refs: list[SourceCitation]
    grounding: Literal["materials", "general_knowledge", "sample"]
    strategy: Strategy
    estimated_minutes: int
    segments: list[PlayerSegment]


class ItemMask:
    """Hides which item of an ordering question is which.

    A lesson gives the items of an ordering question their ids in the order the items
    belong in, so the ids themselves are the answer, and so is any shuffle that can be
    worked out again from what the page knows. What is shown instead is a name made from
    each id with a secret that never leaves the core, in the order of those names. The
    core turns the names back when an answer arrives.
    """

    def __init__(self, secret: bytes) -> None:
        if len(secret) < 16:
            raise ValueError("The secret is too short to hide anything.")
        self._secret = secret

    def _name(self, lesson_id: str, question_id: str, item_id: str, attempt: int) -> str:
        message = "\x1f".join((lesson_id, question_id, item_id, str(attempt))).encode("utf-8")
        digest = hmac.new(self._secret, message, hashlib.sha256).hexdigest()
        # Fits the pattern of an option's id: a letter, then at most fifteen more characters.
        return "o" + digest[:15]

    def names(self, lesson_id: str, item: OrderingItem) -> dict[str, str]:
        """The name each item is shown under, by the item's own id.

        The items are shown in the order of their names. Now and then that order would
        be the right one, which would show the answer; moving one item out of place
        would be worse, because sorting the names would then put it back. So the names
        are made again, differently, until their order is not the answer.
        """
        ids = [entry.id for entry in item.items]
        named: dict[str, str] = {}
        for attempt in range(64):
            named = {item_id: self._name(lesson_id, item.id, item_id, attempt) for item_id in ids}
            if len(ids) < 2 or sorted(ids, key=named.__getitem__) != ids:
                break
        return named

    def real(self, lesson_id: str, item: OrderingItem, given: Sequence[str]) -> tuple[str, ...]:
        """The items' own ids for the names that were shown.

        A name that was never shown becomes nothing, so it is refused when the answer is
        scored: an item's own id is not accepted in place of its name.
        """
        back = {name: item_id for item_id, name in self.names(lesson_id, item).items()}
        return tuple(back.get(name, "") for name in given)

    def __repr__(self) -> str:  # never let the secret out through a repr or a traceback
        return "ItemMask(<secret>)"


def _stable_shuffle[T](items: list[T], *seed: str) -> list[T]:
    """A shuffle that is the same every time for the same seed."""
    digest = hashlib.sha256("\x1f".join(seed).encode("utf-8")).digest()
    # Presentation order only; nothing here needs to be unpredictable.
    generator = random.Random(int.from_bytes(digest[:8], "big"))  # noqa: S311
    shuffled = list(items)
    generator.shuffle(shuffled)
    return shuffled


def player_question(item: AssessmentItem, lesson_id: str, mask: ItemMask) -> PlayerQuestion:
    options: list[PlayerOption] = []
    rubric: list[PlayerRubricPoint] = []
    sample_answer: str | None = None
    unit: str | None = None

    if isinstance(item, ChoiceItem):
        options = _stable_shuffle(
            [PlayerOption(id=option.id, text=option.text) for option in item.options],
            lesson_id,
            item.id,
        )
    elif isinstance(item, OrderingItem):
        names = mask.names(lesson_id, item)
        # In the order of their names: the same on every reload, never the right order,
        # and not something that can be worked out without the secret (a shuffle seeded
        # by the lesson could be).
        options = sorted(
            (PlayerOption(id=names[entry.id], text=entry.text) for entry in item.items),
            key=lambda option: option.id,
        )
    elif isinstance(item, NumericItem):
        unit = item.unit
    elif isinstance(item, ExplanationItem):
        rubric = [PlayerRubricPoint(id=point.id, text=point.text) for point in item.rubric]
        sample_answer = item.sample_answer

    return PlayerQuestion(
        id=item.id,
        form=item.form,
        concept_id=item.concept_id,
        stem=item.stem,
        hint=item.hint,
        difficulty=item.difficulty,
        is_transfer=item.is_transfer,
        options=options,
        unit=unit,
        rubric=rubric,
        sample_answer=sample_answer,
    )


def player_view(lesson: Lesson, mask: ItemMask) -> PlayerLesson:
    """The lesson with every question reduced to what may be shown before answering."""
    segments: list[PlayerSegment] = []
    for segment in lesson.segments:
        if isinstance(segment, CheckpointSegment):
            segments.append(
                PlayerCheckpointSegment(
                    id=segment.id,
                    type="checkpoint",
                    title=segment.title,
                    estimated_seconds=segment.estimated_seconds,
                    narration=segment.narration,
                    question=player_question(segment.question, lesson.lesson_id, mask),
                )
            )
        else:
            segments.append(segment)
    return PlayerLesson(
        schema_version=lesson.schema_version,
        lesson_id=lesson.lesson_id,
        course_id=lesson.course_id,
        title=lesson.title,
        concept_ids=lesson.concept_ids,
        objectives=lesson.objectives,
        source_refs=lesson.source_refs,
        grounding=lesson.grounding,
        strategy=lesson.strategy,
        estimated_minutes=lesson.estimated_minutes,
        segments=segments,
    )
