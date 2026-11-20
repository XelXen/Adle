"""Which questions to ask when a learner practises or reviews a concept.

Pure selection over the questions a concept has. The choice follows what the
evidence still lacks, in this order of importance:

1. a question that would show whether a suspected mistake is real;
2. a question that applies the idea to a new situation, if none has been
   answered correctly yet;
3. a kind of question the learner has not yet answered correctly;
4. a question not seen before, or not seen for the longest time.

A question answered in the last few hours is kept back: the learner has just
seen its explanation, so answering it again would show recall of that
explanation, not of the idea.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from adle_core.learner_model.bkt import Outcome

#: A repeat answer sooner than this counts as an aided one.
FRESH_AGAIN_AFTER = timedelta(hours=12)
DEFAULT_COUNT = 3


@dataclass(frozen=True, slots=True)
class PoolItem:
    """One question that can be asked about a concept."""

    lesson_id: str
    question_id: str
    form: str
    is_transfer: bool = False
    difficulty: int = 2
    #: The kinds of mistake this question is able to reveal.
    reveals: frozenset[str] = frozenset()
    last_answered_at: datetime | None = None
    last_outcome: Outcome | None = None

    def is_fresh(self, now: datetime) -> bool:
        """Whether an answer now would be evidence, rather than an echo of a recent one."""
        return self.last_answered_at is None or now - self.last_answered_at >= FRESH_AGAIN_AFTER


@dataclass(frozen=True, slots=True)
class Need:
    """What the evidence for a concept still lacks."""

    forms_correct: frozenset[str] = frozenset()
    transfer_correct: int = 0
    #: Kinds of mistake to check for, the most important first.
    to_check: tuple[str, ...] = ()


def fresh_items(pool: Sequence[PoolItem], now: datetime) -> list[PoolItem]:
    return [item for item in pool if item.is_fresh(now)]


def _score(item: PoolItem, need: Need, now: datetime) -> float:
    score = 0.0
    for rank, kind in enumerate(need.to_check):
        if kind in item.reveals:
            score += 100.0 - rank  # the first thing to check outweighs the rest
            break
    if item.is_transfer and need.transfer_correct == 0:
        score += 30.0
    if item.form not in need.forms_correct:
        score += 20.0
    if item.last_answered_at is None:
        score += 15.0
    else:
        days = (now - item.last_answered_at) / timedelta(days=1)
        score += min(days, 30.0) * 0.5
        if item.last_outcome in (Outcome.INCORRECT, Outcome.PARTIAL):
            score += 10.0
    return score


def choose(
    pool: Sequence[PoolItem], need: Need, now: datetime, *, count: int = DEFAULT_COUNT
) -> list[PoolItem]:
    """Up to ``count`` questions worth asking now, the most useful first.

    Only questions whose answer would count as evidence are chosen. The result
    may be shorter than ``count``, or empty: then there is nothing useful to
    ask yet, and saying so is better than asking anyway.
    """
    remaining = sorted(
        fresh_items(pool, now),
        key=lambda item: (item.difficulty, item.lesson_id, item.question_id),
    )
    chosen: list[PoolItem] = []
    while remaining and len(chosen) < count:
        forms_taken = {item.form for item in chosen}
        best = max(
            remaining,
            # A second question of a form already picked is worth a little less: variety
            # is itself part of the evidence.
            key=lambda item: _score(item, need, now) - (10.0 if item.form in forms_taken else 0.0),
        )
        chosen.append(best)
        remaining.remove(best)
    return chosen


def next_fresh_at(pool: Sequence[PoolItem], now: datetime) -> datetime | None:
    """When the first kept-back question becomes worth asking again, if any is kept back."""
    waiting = [
        item.last_answered_at + FRESH_AGAIN_AFTER
        for item in pool
        if item.last_answered_at is not None and not item.is_fresh(now)
    ]
    return min(waiting) if waiting else None
