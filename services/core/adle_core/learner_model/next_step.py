"""What to do next in a course, and why.

A deterministic policy over what is known about each concept. It proposes one
step and a few alternatives; the learner is free to take any of them or none.
Every step carries one sentence of reason that the learner could disagree
with, because a suggestion nobody can argue with is an order.

The order of concerns, most pressing first:

1. finish what was started;
2. something that is going wrong (the learner said an explanation did not
   help, a hypothesis supported by more than one answer, or a run of answers
   that did not go well): look at what the concept builds on, or try a
   different explanation, never simply the same lesson again;
3. a review that is due;
4. a suspicion worth one question;
5. the next concept, with practice where the evidence is thin beside it;
6. nothing: say so, and say when there will be something.

No rule here looks at a score. The inputs are states, counts, and dates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from adle_core.learner_model.bkt import Outcome
from adle_core.learner_model.mastery import (
    MISUNDERSTANDING_TO_CLEAR,
    STATE_LABELS,
    MasteryState,
)
from adle_core.learner_model.misconceptions import Hypothesis, Status, needing_a_check

#: A run of recent answers is "not going well" when this many of the last few missed.
STRUGGLE_WINDOW = 4
STRUGGLE_MISSES = 3
MAX_ALTERNATIVES = 3
#: More explanations of one concept than this stop helping; the policy then looks elsewhere.
MAX_LESSONS_PER_CONCEPT = 4

#: Said beside any suggestion that comes from things going badly.
PAUSE_NOTE = "It’s also fine to stop for today. A break often helps more than pushing on."


class StepKind(StrEnum):
    ADD_CONCEPTS = "add_concepts"
    RESUME_LESSON = "resume_lesson"
    REVISIT_PREREQUISITE = "revisit_prerequisite"
    CHECK = "check"
    ANOTHER_EXPLANATION = "another_explanation"
    REVIEW = "review"
    PRACTISE = "practise"
    START_LESSON = "start_lesson"
    REPEAT_LESSON = "repeat_lesson"
    CREATE_LESSON = "create_lesson"
    NOTHING_DUE = "nothing_due"


@dataclass(frozen=True, slots=True)
class LessonStatus:
    id: str
    title: str
    started: bool
    completed: bool
    #: When the learner last moved in it, if they have.
    touched_at: datetime | None = None
    #: When the lesson was added to the course.
    added_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ConceptStatus:
    """Everything the policy may know about one concept."""

    id: str
    title: str
    #: Ids of the concepts this one needs first.
    prerequisites: tuple[str, ...] = ()
    state: MasteryState = MasteryState.NOT_ASSESSED
    #: What is still needed before "Demonstrated for now", in words.
    missing: tuple[str, ...] = ()
    answered: int = 0
    #: The learner has said they know some or all of this already.
    claims_familiarity: bool = False
    review_due_at: datetime | None = None
    lessons: tuple[LessonStatus, ...] = ()
    #: Questions whose answer would count as evidence right now.
    fresh_questions: int = 0
    #: Kinds of mistake that a fresh question could reveal.
    checkable: frozenset[str] = frozenset()
    hypotheses: tuple[Hypothesis, ...] = ()
    #: Outcomes of the most recent scored answers, oldest first.
    recent: tuple[Outcome, ...] = ()
    #: The learner said an explanation of this concept did not help, and no other
    #: explanation has been added since.
    asked_for_another: bool = False

    @property
    def demonstrated(self) -> bool:
        return self.state is MasteryState.DEMONSTRATED

    @property
    def lesson_completed(self) -> bool:
        return any(lesson.completed for lesson in self.lessons)

    @property
    def worked_on(self) -> bool:
        """Whether there is any reason to think the learner has met this concept."""
        return self.lesson_completed or self.answered > 0 or self.claims_familiarity

    @property
    def struggling(self) -> bool:
        window = self.recent[-STRUGGLE_WINDOW:]
        misses = sum(1 for outcome in window if outcome is Outcome.INCORRECT)
        return len(window) >= STRUGGLE_WINDOW and misses >= STRUGGLE_MISSES

    @property
    def can_add_lesson(self) -> bool:
        return len(self.lessons) < MAX_LESSONS_PER_CONCEPT


@dataclass(frozen=True, slots=True)
class Step:
    kind: StepKind
    #: What the button says.
    title: str
    #: Why this, in one or two sentences. Never a score.
    reason: str
    concept_id: str | None = None
    lesson_id: str | None = None
    #: The kind of mistake a check is about, when it is about one.
    about: str | None = None
    #: The step needs the AI provider, and no key is set up.
    needs_key: bool = False

    @property
    def identity(self) -> tuple[StepKind, str | None, str | None]:
        return (self.kind, self.concept_id, self.lesson_id)


@dataclass(frozen=True, slots=True)
class Plan:
    recommended: Step
    #: Other reasonable things to do instead, the most useful first.
    alternatives: tuple[Step, ...] = ()
    #: Something worth saying beside the suggestion (that stopping is fine, for one).
    note: str | None = None


def _days(span: timedelta) -> str:
    days = max(0, round(span / timedelta(days=1)))
    if days == 0:
        return "today"
    return "a day" if days == 1 else f"{days} days"


def _names(concepts: Sequence[ConceptStatus]) -> str:
    titles = [f"“{concept.title}”" for concept in concepts]
    if len(titles) <= 2:
        return " and ".join(titles)
    return ", ".join(titles[:-1]) + f", and {titles[-1]}"


def _weak_prerequisites(
    concept: ConceptStatus, by_id: dict[str, ConceptStatus]
) -> list[ConceptStatus]:
    """What the concept builds on that is not yet demonstrated, in learning order."""
    return [
        by_id[needed]
        for needed in concept.prerequisites
        if needed in by_id and not by_id[needed].demonstrated
    ]


def _lesson_for(concept: ConceptStatus) -> LessonStatus | None:
    """The lesson to open for a concept: one in progress, else one not started, else any."""
    in_progress = [lesson for lesson in concept.lessons if lesson.started and not lesson.completed]
    if in_progress:
        return in_progress[0]
    untouched = [lesson for lesson in concept.lessons if not lesson.started]
    if untouched:
        return untouched[0]
    return concept.lessons[-1] if concept.lessons else None


def _revisit(concept: ConceptStatus, weak: Sequence[ConceptStatus], why: str) -> Step | None:
    """Go back to the first thing a concept builds on that is not solid, if it can be studied."""
    for needed in weak:
        lesson = _lesson_for(needed)
        if lesson is not None:
            return Step(
                kind=StepKind.REVISIT_PREREQUISITE,
                title=f"Revisit “{needed.title}”",
                reason=f"{why} “{concept.title}” builds on “{needed.title}”, which isn’t solid "
                "yet. Start there.",
                concept_id=needed.id,
                lesson_id=lesson.id,
            )
        if needed.fresh_questions > 0:
            return Step(
                kind=StepKind.PRACTISE,
                title=f"Practise “{needed.title}”",
                reason=f"{why} “{concept.title}” builds on “{needed.title}”, which isn’t solid "
                "yet. A few questions on it come first.",
                concept_id=needed.id,
            )
    return None


def _another_way(concept: ConceptStatus, why: str, can_generate: bool) -> Step | None:
    """A different explanation of the same concept: one already there, or a new one."""
    untried = [lesson for lesson in concept.lessons if not lesson.started]
    if untried and concept.lesson_completed:
        return Step(
            kind=StepKind.START_LESSON,
            title=f"Try “{untried[0].title}”",
            reason=f"{why} There’s another explanation you haven’t tried.",
            concept_id=concept.id,
            lesson_id=untried[0].id,
        )
    if concept.can_add_lesson:
        return Step(
            kind=StepKind.ANOTHER_EXPLANATION,
            title=f"Try another explanation of “{concept.title}”",
            reason=f"{why} A different explanation may work better than repeating the same lesson.",
            concept_id=concept.id,
            needs_key=not can_generate,
        )
    return None


def _untried(concept: ConceptStatus) -> tuple[Step, bool] | None:
    """An explanation not opened yet, of a concept the learner already has another one for.

    The flag says whether it was added after the learner last touched the others. A lesson
    is only ever added because the learner asked for it, so then it is what they are
    waiting for, and it comes before going on with the old one.
    """
    if concept.demonstrated:
        return None
    opened = [lesson for lesson in concept.lessons if lesson.started]
    untried = [lesson for lesson in concept.lessons if not lesson.started]
    if not opened or not untried:
        return None
    newest = untried[-1]
    asked_for = newest.added_at is not None and all(
        lesson.touched_at is None or newest.added_at > lesson.touched_at for lesson in opened
    )
    step = Step(
        kind=StepKind.START_LESSON,
        title=f"Try “{newest.title}”",
        reason=f"There’s another explanation of “{concept.title}” you haven’t tried.",
        concept_id=concept.id,
        lesson_id=newest.id,
    )
    return step, asked_for


def _trouble(
    concept: ConceptStatus, by_id: dict[str, ConceptStatus], can_generate: bool
) -> list[Step]:
    """Steps for a concept where something is going wrong."""
    steps: list[Step] = []
    weak = _weak_prerequisites(concept, by_id)

    if concept.asked_for_another and not concept.demonstrated:
        # The learner asked. That comes before anything Adle infers.
        step = _another_way(
            concept, f"You said an explanation of “{concept.title}” didn’t help.", can_generate
        )
        if step is not None:
            steps.append(step)

    for hypothesis in concept.hypotheses:
        if not hypothesis.blocks_mastery:
            continue
        why = f"More than one answer on “{concept.title}” suggests that {hypothesis.label}."
        if hypothesis.kind == "prerequisite_gap":
            revisit = _revisit(concept, weak, why)
            if revisit is not None:
                steps.append(revisit)
                continue
        if hypothesis.kind in concept.checkable:
            steps.append(
                Step(
                    kind=StepKind.CHECK,
                    title=f"Check “{concept.title}”",
                    reason=f"{why} A few questions will show whether it still holds.",
                    concept_id=concept.id,
                    about=hypothesis.kind,
                )
            )

    if concept.struggling and not concept.demonstrated:
        why = f"Your last few answers on “{concept.title}” didn’t go well."
        # More of the same lesson is the one thing not to suggest here.
        step = _revisit(concept, weak, why) or _another_way(concept, why, can_generate)
        if step is not None:
            steps.append(step)
    return steps


def _review(concept: ConceptStatus, now: datetime) -> Step | None:
    due = concept.review_due_at
    if due is None or due > now or concept.fresh_questions == 0:
        return None
    overdue = now - due
    when = "is due today" if overdue < timedelta(days=1) else f"was due {_days(overdue)} ago"
    return Step(
        kind=StepKind.REVIEW,
        title=f"Review “{concept.title}”",
        reason=f"A review of “{concept.title}” {when}. Recalling it after a gap is what makes it "
        "stick.",
        concept_id=concept.id,
    )


def _suspicion(concept: ConceptStatus) -> Step | None:
    for hypothesis in concept.hypotheses:
        if (
            hypothesis.status is Status.TENTATIVE
            and not hypothesis.is_slip
            and hypothesis.kind in concept.checkable
        ):
            return Step(
                kind=StepKind.CHECK,
                title=f"Check “{concept.title}”",
                reason=f"One answer on “{concept.title}” suggested that {hypothesis.label}. A "
                "question or two will check.",
                concept_id=concept.id,
                about=hypothesis.kind,
            )
    return None


def _within_reach(concept: ConceptStatus) -> list[str]:
    """What is still needed that questions asked right now could supply.

    A misunderstanding that no fresh question can show is left out: other questions will
    not clear it, and suggesting practice "to clear it up" would not be true. The check
    is suggested in its own right as soon as a question that would show it can be asked.
    """
    can_be_checked = any(
        hypothesis.blocks_mastery and hypothesis.kind in concept.checkable
        for hypothesis in concept.hypotheses
    )
    return [item for item in concept.missing if item != MISUNDERSTANDING_TO_CLEAR or can_be_checked]


def _practise(concept: ConceptStatus) -> Step | None:
    if concept.demonstrated or not concept.worked_on or concept.fresh_questions == 0:
        return None
    within_reach = _within_reach(concept)
    if concept.missing and not within_reach:
        # All that is missing is a check that cannot be made yet. That needs time, not practice.
        return None
    needed = "; ".join(within_reach)
    return Step(
        kind=StepKind.PRACTISE,
        title=f"Practise “{concept.title}”",
        reason=f"“{concept.title}” is at “{STATE_LABELS[concept.state]}”."
        + (f" Still needed: {needed}." if needed else ""),
        concept_id=concept.id,
    )


def _advance(
    concept: ConceptStatus, by_id: dict[str, ConceptStatus], can_generate: bool
) -> Step | None:
    """Begin the lesson of a concept that has not been worked through."""
    if concept.lesson_completed or concept.demonstrated:
        return None
    if any(lesson.started for lesson in concept.lessons):
        # A lesson in progress is offered as something to continue, not to start.
        return None
    if concept.asked_for_another:
        # They said its explanation did not help; that request is answered elsewhere.
        return None
    needs = [by_id[needed] for needed in concept.prerequisites if needed in by_id]
    unmet = [needed for needed in needs if not needed.worked_on]
    if unmet:
        # The earlier concept will be suggested in its own right; this one waits.
        return None
    builds_on = (
        f"It builds on {_names(needs)}, which you’ve covered."
        if needs
        else "It has no prerequisites."
    )
    if concept.claims_familiarity and concept.answered == 0 and concept.fresh_questions > 0:
        # They say they know it. Checking is quicker than teaching it again, and kinder.
        return Step(
            kind=StepKind.PRACTISE,
            title=f"Check what you know about “{concept.title}”",
            reason=f"You said you already know “{concept.title}”. A few questions will confirm "
            "it, and then you can skip the lesson.",
            concept_id=concept.id,
        )
    lesson = _lesson_for(concept)
    if lesson is None:
        return Step(
            kind=StepKind.CREATE_LESSON,
            title=f"Create a lesson for “{concept.title}”",
            reason=f"“{concept.title}” is next in your course and has no lesson yet. {builds_on}",
            concept_id=concept.id,
            needs_key=not can_generate,
        )
    return Step(
        kind=StepKind.START_LESSON,
        title=f"Start “{lesson.title}”",
        reason=f"“{concept.title}” is next in your course. {builds_on}",
        concept_id=concept.id,
        lesson_id=lesson.id,
    )


def _nothing(order: Sequence[ConceptStatus], now: datetime) -> Step:
    upcoming = sorted(
        (concept for concept in order if concept.review_due_at and concept.review_due_at > now),
        key=lambda concept: concept.review_due_at or now,
    )
    if all(concept.demonstrated for concept in order):
        reason = "You’ve covered every concept in this course for now."
    else:
        reason = "Nothing to do right now. What you answered recently needs time to settle."
    if upcoming:
        first = upcoming[0]
        wait = (first.review_due_at or now) - now
        reason += f" Next review: “{first.title}”, in {_days(wait)}."
    return Step(kind=StepKind.NOTHING_DUE, title="Nothing is due", reason=reason)


def plan(order: Sequence[ConceptStatus], now: datetime, *, can_generate: bool) -> Plan:
    """The step to suggest for a course whose concepts are given in learning order."""
    if not order:
        return Plan(
            Step(
                kind=StepKind.ADD_CONCEPTS,
                title="Add concepts",
                reason="This course has no concepts yet.",
            )
        )
    by_id = {concept.id: concept for concept in order}
    candidates: list[Step] = []

    # 1. Finish what was started, most recently touched first.
    in_progress = sorted(
        (
            (lesson, concept)
            for concept in order
            for lesson in concept.lessons
            if lesson.started and not lesson.completed
        ),
        key=lambda pair: pair[0].touched_at or datetime.min.replace(tzinfo=now.tzinfo),
        reverse=True,
    )
    untried = {concept.id: found for concept in order if (found := _untried(concept)) is not None}
    # An explanation the learner asked for and has not opened yet is what they are waiting for.
    candidates.extend(step for step, asked_for in untried.values() if asked_for)
    waiting_for = {concept_id for concept_id, (_, asked_for) in untried.items() if asked_for}

    # Offered only after everything else: see the end of this function.
    last_resort: list[Step] = []
    for lesson, concept in in_progress:
        resume = Step(
            kind=StepKind.RESUME_LESSON,
            title=f"Continue “{lesson.title}”",
            reason="You stopped partway through this lesson.",
            concept_id=concept.id,
            lesson_id=lesson.id,
        )
        # A lesson the learner said did not help, or asked for a replacement of, is not
        # pressed on them again.
        set_aside = concept.asked_for_another or concept.id in waiting_for
        (last_resort if set_aside else candidates).append(resume)

    # 2. Something is going wrong.
    trouble = [step for concept in order for step in _trouble(concept, by_id, can_generate)]
    candidates.extend(trouble)

    # 3. Reviews that are due, the longest overdue first.
    due = [concept for concept in order if _review(concept, now) is not None]
    for concept in sorted(due, key=lambda item: item.review_due_at or now):
        step = _review(concept, now)
        if step is not None:
            candidates.append(step)

    # 4. Suspicions worth a question.
    candidates.extend(step for concept in order if (step := _suspicion(concept)) is not None)

    # 5. The next concept, then practice where the evidence is thin. Moving on comes first:
    #    practice is always offered beside it, never in front of it.
    advance = [step for concept in order if (step := _advance(concept, by_id, can_generate))]
    practise = [step for concept in order if (step := _practise(concept)) is not None]
    candidates.extend(advance[:1])
    candidates.extend(practise)
    candidates.extend(step for step, asked_for in untried.values() if not asked_for)
    candidates.extend(advance[1:])

    # A lesson already finished can always be gone through again; offered last, and never
    # where the answers say that more of the same is not helping.
    for concept in order:
        finished = [lesson for lesson in concept.lessons if lesson.completed]
        stuck = concept.struggling or concept.asked_for_another
        if finished and not concept.demonstrated and not stuck:
            last_resort.append(
                Step(
                    kind=StepKind.REPEAT_LESSON,
                    title=f'Go through "{finished[-1].title}" again',
                    reason=f"You’ve finished this lesson, and “{concept.title}” is at "
                    f"“{STATE_LABELS[concept.state]}”.",
                    concept_id=concept.id,
                    lesson_id=finished[-1].id,
                )
            )

    unique: list[Step] = []
    seen: set[tuple[StepKind, str | None, str | None]] = set()
    for step in candidates:
        if step.identity not in seen:
            seen.add(step.identity)
            unique.append(step)
    last_resort = [step for step in last_resort if step.identity not in seen]

    # What can be done now comes first. A step that needs a key the learner has not set up
    # comes after it, and more of a lesson already seen comes after everything else.
    doable = [step for step in unique if not step.needs_key]
    needs_key = [step for step in unique if step.needs_key]
    if doable:
        ranked = [*doable, *needs_key, *last_resort]
    elif needs_key:
        ranked = [*needs_key, *last_resort]
    else:
        ranked = [_nothing(order, now), *last_resort]
    recommended, *others = ranked
    troubled = {step.identity for step in trouble}
    return Plan(
        recommended=recommended,
        alternatives=tuple(others[:MAX_ALTERNATIVES]),
        note=PAUSE_NOTE if recommended.identity in troubled else None,
    )


class PracticePurpose(StrEnum):
    REVIEW = "review"
    CHECK = "check"
    PRACTISE = "practise"


def practice_purpose(
    concept: ConceptStatus, now: datetime, *, about: str | None = None
) -> tuple[PracticePurpose, str]:
    """Why a set of questions on a concept is being asked, and the reason to show with them.

    ``about`` names the kind of mistake the learner chose to check, when they came from a
    suggestion that was about one.
    """
    worth_checking = [
        hypothesis
        for hypothesis in needing_a_check(concept.hypotheses)
        if hypothesis.kind in concept.checkable
    ]
    chosen = next((hypothesis for hypothesis in worth_checking if hypothesis.kind == about), None)
    review = _review(concept, now)
    if chosen is None and review is not None:
        return PracticePurpose.REVIEW, review.reason
    target = chosen or (worth_checking[0] if worth_checking else None)
    if target is not None:
        if target.status is Status.SUPPORTED:
            return (
                PracticePurpose.CHECK,
                f"More than one answer on “{concept.title}” suggests that {target.label}. These "
                "questions will show whether it still holds.",
            )
        return (
            PracticePurpose.CHECK,
            f"One answer on “{concept.title}” suggested that {target.label}. These questions will "
            "check.",
        )
    if concept.claims_familiarity and concept.answered == 0:
        return (
            PracticePurpose.PRACTISE,
            f"You said you already know “{concept.title}”. These questions will confirm it.",
        )
    label = STATE_LABELS[concept.state]
    if concept.demonstrated:
        return (
            PracticePurpose.PRACTISE,
            f"“{concept.title}” is at “{label}”. This is extra practice.",
        )
    needed = "; ".join(_within_reach(concept))
    if concept.missing and not needed:
        return (
            PracticePurpose.PRACTISE,
            f"“{concept.title}” is at “{label}”. The question that would settle it can be asked "
            "again later. This is extra practice in the meantime.",
        )
    return (
        PracticePurpose.PRACTISE,
        f"“{concept.title}” is at “{label}”." + (f" Still needed: {needed}." if needed else ""),
    )
