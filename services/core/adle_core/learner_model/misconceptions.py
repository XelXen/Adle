"""What a pattern of wrong answers might mean, held as a hypothesis until it is checked.

A wrong option can point at a kind of mistake ("mixed up two terms"). One such
answer is a suspicion, not a diagnosis. This module turns the record of a
concept's answers into hypotheses with a status, by rules that can be read and
replayed:

* the first answer that points at a kind of mistake opens a **tentative**
  hypothesis;
* a second, independent answer pointing the same way makes it **supported**;
* a correct, unaided answer to a question that *could* have shown the mistake
  **rejects** a tentative hypothesis, and two of them **resolve** a supported
  one;
* the learner may dismiss one ("that was a slip"), which rejects it.

Only a supported hypothesis about the idea itself stands in the way of
"Demonstrated for now". Slips of arithmetic or of reading are noted, counted
as partly right (``tracing``), and never treated as a gap in understanding.

Nothing here is stored: hypotheses are computed from the attempts and the
learner's dismissals whenever they are needed, so they can never drift from
the record they come from.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from adle_core.learner_model.bkt import Outcome

#: The kinds of mistake Adle distinguishes, with how each is put to the learner.
KIND_LABELS: dict[str, str] = {
    "prerequisite_gap": "something this builds on may be missing",
    "definition_confusion": "two terms may be getting mixed up",
    "notation_confusion": "a symbol may be read as something else",
    "procedure_order": "the steps may be in a different order than they need to be",
    "causal_confusion": "what causes what may be the other way round",
    "arithmetic_slip": "a slip in the arithmetic rather than in the idea",
    "misread_question": "the question may have been read differently than it was meant",
    "overgeneralization": "a rule may be applied further than it holds",
}

#: Mistakes of execution, not of understanding. Noted, counted as partly right, never
#: held against mastery, and never a reason to re-teach.
SLIPS = frozenset({"arithmetic_slip", "misread_question"})

#: Answers to the same question closer together than this are one piece of evidence.
INDEPENDENT_AFTER = timedelta(hours=12)
#: Correct answers needed to resolve a supported hypothesis.
ANSWERS_TO_RESOLVE = 2


class Status(StrEnum):
    #: Suggested once. Worth a question that would tell, not worth acting on.
    TENTATIVE = "tentative"
    #: Suggested by independent answers. Treated as real until shown otherwise.
    SUPPORTED = "supported"
    #: Checked and not found, or dismissed by the learner.
    REJECTED = "rejected"
    #: Was supported; later answers show it is gone.
    RESOLVED = "resolved"


OPEN = frozenset({Status.TENTATIVE, Status.SUPPORTED})


@dataclass(frozen=True, slots=True)
class Answer:
    """One scored answer, as far as hypotheses are concerned."""

    occurred_at: datetime
    question_id: str
    outcome: Outcome
    hinted: bool = False
    unsure: bool = False
    #: The kind of mistake this particular answer points at, if any.
    suggests: str | None = None
    #: Every kind of mistake this question is able to reveal.
    reveals: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Dismissal:
    """The learner said a hypothesis does not describe them."""

    occurred_at: datetime
    kind: str


@dataclass(frozen=True, slots=True)
class Hypothesis:
    kind: str
    status: Status
    #: Answers that pointed at this mistake since it was last opened.
    suggested: int
    #: Correct answers, since it became supported, to questions that could have shown it.
    countered: int
    first_seen_at: datetime
    last_changed_at: datetime
    #: The question and time of the latest answer that pointed at it.
    last_question: str
    last_suggested_at: datetime
    dismissed_by_learner: bool = False

    @property
    def is_open(self) -> bool:
        return self.status in OPEN

    @property
    def is_slip(self) -> bool:
        return self.kind in SLIPS

    @property
    def blocks_mastery(self) -> bool:
        return self.status is Status.SUPPORTED and not self.is_slip

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, "a mistake of a kind Adle has no name for")

    def describe(self) -> str:
        """Where this stands, for the learner: what was noticed and what Adle will do about it."""
        if self.is_slip:
            if self.is_open:
                return f"Noticed: {self.label}. It is treated as a slip, not as a gap."
            return f"Earlier: {self.label}. Not seen since."
        if self.status is Status.TENTATIVE:
            return (
                f"One answer suggested that {self.label}. One answer is not enough to say: "
                "Adle will ask a question that would show it."
            )
        if self.status is Status.SUPPORTED:
            return (
                f"More than one answer suggests that {self.label}. The next steps come back to it."
            )
        if self.status is Status.RESOLVED:
            return (
                f"Earlier answers suggested that {self.label}. "
                "Your later answers show it is sorted."
            )
        if self.dismissed_by_learner:
            return (
                f"An answer suggested that {self.label}. "
                "You said it was a slip, so it is set aside."
            )
        return f"One answer suggested that {self.label}. A later question did not show it."


def _suggest(current: Hypothesis | None, answer: Answer, kind: str) -> Hypothesis:
    if current is None or not current.is_open:
        # New, or reopened after being rejected or resolved: start again from one answer.
        return Hypothesis(
            kind=kind,
            status=Status.TENTATIVE,
            suggested=1,
            countered=0,
            first_seen_at=current.first_seen_at if current else answer.occurred_at,
            last_changed_at=answer.occurred_at,
            last_question=answer.question_id,
            last_suggested_at=answer.occurred_at,
        )
    independent = (
        answer.question_id != current.last_question
        or answer.occurred_at - current.last_suggested_at >= INDEPENDENT_AFTER
    )
    status = current.status
    changed_at = current.last_changed_at
    if status is Status.TENTATIVE and independent:
        status, changed_at = Status.SUPPORTED, answer.occurred_at
    return replace(
        current,
        status=status,
        suggested=current.suggested + (1 if independent else 0),
        # Pointing at it again undoes any progress towards resolving it.
        countered=0,
        last_changed_at=changed_at,
        last_question=answer.question_id,
        last_suggested_at=answer.occurred_at,
    )


def _counter(current: Hypothesis, answer: Answer) -> Hypothesis:
    if current.status is Status.TENTATIVE:
        return replace(current, status=Status.REJECTED, last_changed_at=answer.occurred_at)
    countered = current.countered + 1
    if countered >= ANSWERS_TO_RESOLVE:
        return replace(
            current,
            status=Status.RESOLVED,
            countered=countered,
            last_changed_at=answer.occurred_at,
        )
    return replace(current, countered=countered)


def fold(events: Iterable[Answer | Dismissal]) -> dict[str, Hypothesis]:
    """The hypotheses a concept's answers and dismissals add up to, by kind.

    ``events`` may be in any order; they are applied oldest first.
    """
    hypotheses: dict[str, Hypothesis] = {}
    for event in sorted(events, key=lambda item: item.occurred_at):
        if isinstance(event, Dismissal):
            current = hypotheses.get(event.kind)
            if current is not None and current.is_open:
                hypotheses[event.kind] = replace(
                    current,
                    status=Status.REJECTED,
                    last_changed_at=event.occurred_at,
                    dismissed_by_learner=True,
                )
            continue

        if event.outcome is Outcome.SKIPPED:
            continue
        if event.outcome is not Outcome.CORRECT:
            if event.suggests in KIND_LABELS:
                hypotheses[event.suggests] = _suggest(
                    hypotheses.get(event.suggests), event, event.suggests
                )
            continue
        # A right answer after a hint, or one the learner was unsure of, shows too little
        # to clear anything.
        if event.hinted or event.unsure:
            continue
        for kind in event.reveals:
            current = hypotheses.get(kind)
            if current is not None and current.is_open:
                hypotheses[kind] = _counter(current, event)
    return hypotheses


def blocks_mastery(hypotheses: Iterable[Hypothesis]) -> bool:
    """Whether any hypothesis stands in the way of "Demonstrated for now"."""
    return any(hypothesis.blocks_mastery for hypothesis in hypotheses)


def needing_a_check(hypotheses: Iterable[Hypothesis]) -> list[Hypothesis]:
    """Open hypotheses about the idea itself, most established first: what to ask about next."""
    wanted = [h for h in hypotheses if h.is_open and not h.is_slip]
    return sorted(
        wanted, key=lambda h: (h.status is not Status.SUPPORTED, -h.suggested, h.first_seen_at)
    )


def describe_change(before: Mapping[str, Hypothesis], after: Mapping[str, Hypothesis]) -> str:
    """What one more answer changed about the hypotheses, for the learner. Empty if nothing.

    Said as a possibility about the idea, never as a fault of the person, and never
    stronger than the evidence: one answer "could mean", two "suggest".
    """
    sentences: list[str] = []
    for kind in sorted(after, key=lambda name: after[name].last_changed_at):
        now = after[kind]
        was = before.get(kind)
        if was == now:
            continue
        opened = was is None or not was.is_open
        if now.is_slip:
            # The answer itself is already described as a slip (``tracing``).
            continue
        if now.status is Status.TENTATIVE and opened:
            sentences.append(
                f"That answer could mean that {now.label}. One answer is not enough to say, "
                "so Adle will ask a question that would show it."
            )
        elif now.status is Status.SUPPORTED and (was is None or was.status is Status.TENTATIVE):
            sentences.append(
                f"This is the second answer suggesting that {now.label}, "
                "so the next steps come back to it."
            )
        elif now.status is Status.REJECTED and was is not None and was.is_open:
            sentences.append(
                f"An earlier answer suggested that {now.label}. This one shows otherwise, "
                "so that is set aside."
            )
        elif now.status is Status.RESOLVED:
            sentences.append(
                f"Earlier answers suggested that {now.label}. "
                "Your recent answers show it is sorted."
            )
        elif (
            now.status is Status.SUPPORTED
            and was is not None
            and was.status is Status.SUPPORTED
            and now.countered > was.countered
        ):
            sentences.append(
                f"Earlier answers suggested that {now.label}. This one goes against that; "
                "one more like it settles it."
            )
    return " ".join(sentences)
