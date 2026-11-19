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
import random
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


def _stable_shuffle[T](items: list[T], *seed: str) -> list[T]:
    """A shuffle that is the same every time for the same seed."""
    digest = hashlib.sha256("\x1f".join(seed).encode("utf-8")).digest()
    # Presentation order only; nothing here needs to be unpredictable.
    generator = random.Random(int.from_bytes(digest[:8], "big"))  # noqa: S311
    shuffled = list(items)
    generator.shuffle(shuffled)
    return shuffled


def player_question(item: AssessmentItem, lesson_id: str) -> PlayerQuestion:
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
        in_order = [PlayerOption(id=entry.id, text=entry.text) for entry in item.items]
        options = _stable_shuffle(in_order, lesson_id, item.id)
        if options == in_order:
            # Showing the items already in order would give the answer away.
            options = [*in_order[1:], in_order[0]]
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


def player_view(lesson: Lesson) -> PlayerLesson:
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
                    question=player_question(segment.question, lesson.lesson_id),
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
