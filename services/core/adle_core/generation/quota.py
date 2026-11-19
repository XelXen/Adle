"""How much of the provider's allowance may be used, and when.

Pure rules: no clock, no database, no network. The caller passes in the
requests that have been made and the present moment, and gets back a decision.

The provider enforces its own limits per account, and other apps using the
same key count against them too. What is computed here is therefore a *local
estimate* kept deliberately below the documented limits, so that Adle is never
the reason an account runs out. The interface must present it as an estimate.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

MINUTE = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class QuotaLimits:
    """Safety margins under the provider's documented limits (5/min, 100/day, 1M tokens/day)."""

    requests_per_minute: int = 4
    requests_per_day: int = 90
    tokens_per_day: int = 900_000

    def __post_init__(self) -> None:
        if min(self.requests_per_minute, self.requests_per_day, self.tokens_per_day) < 1:
            raise ValueError("every limit must be at least 1")


DEFAULT_LIMITS = QuotaLimits()


@dataclass(frozen=True, slots=True)
class UsageEntry:
    """One request that was sent, whatever came back."""

    started_at: datetime
    #: Prompt plus completion tokens: as reported by the provider, or estimated.
    tokens: int


class Verdict(StrEnum):
    ALLOWED = "allowed"
    #: The last minute is full. Waiting ``wait_seconds`` is enough.
    WAIT = "wait"
    #: Today's allowance is used up. Nothing more until ``resets_at``.
    EXHAUSTED = "exhausted"


@dataclass(frozen=True, slots=True)
class Decision:
    verdict: Verdict
    wait_seconds: float = 0.0
    resets_at: datetime | None = None
    #: Which daily limit ran out, for the message shown to the learner.
    exhausted: str | None = None


@dataclass(frozen=True, slots=True)
class UsageSummary:
    requests_today: int
    tokens_today: int
    requests_last_minute: int
    limits: QuotaLimits
    #: When the daily counts start again.
    resets_at: datetime


def day_start(moment: datetime) -> datetime:
    """The start of the provider's day that contains ``moment``.

    The provider does not document when its daily window resets. UTC midnight
    is assumed, which is one more reason the totals are an estimate.
    """
    moment = moment.astimezone(UTC)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def next_reset(moment: datetime) -> datetime:
    return day_start(moment) + timedelta(days=1)


def summarise(
    entries: Iterable[UsageEntry], now: datetime, limits: QuotaLimits = DEFAULT_LIMITS
) -> UsageSummary:
    recorded = list(entries)
    start = day_start(now)
    today = [entry for entry in recorded if start <= entry.started_at <= now]
    return UsageSummary(
        requests_today=len(today),
        tokens_today=sum(max(0, entry.tokens) for entry in today),
        # The minute window does not stop at midnight: a request late yesterday still fills it.
        requests_last_minute=sum(
            1 for entry in recorded if timedelta(0) <= now - entry.started_at < MINUTE
        ),
        limits=limits,
        resets_at=next_reset(now),
    )


def decide(
    entries: Iterable[UsageEntry],
    now: datetime,
    *,
    estimated_tokens: int,
    limits: QuotaLimits = DEFAULT_LIMITS,
) -> Decision:
    """Whether one more request of about ``estimated_tokens`` may be sent now."""
    recorded = list(entries)
    summary = summarise(recorded, now, limits)

    if summary.requests_today >= limits.requests_per_day:
        return Decision(Verdict.EXHAUSTED, resets_at=summary.resets_at, exhausted="requests")
    if summary.tokens_today + max(0, estimated_tokens) > limits.tokens_per_day:
        return Decision(Verdict.EXHAUSTED, resets_at=summary.resets_at, exhausted="tokens")

    recent = sorted(
        entry.started_at for entry in recorded if timedelta(0) <= now - entry.started_at < MINUTE
    )
    if len(recent) >= limits.requests_per_minute:
        # Room opens when the oldest request that still counts leaves the window.
        leaves = recent[len(recent) - limits.requests_per_minute] + MINUTE
        return Decision(Verdict.WAIT, wait_seconds=max(0.0, (leaves - now).total_seconds()))
    return Decision(Verdict.ALLOWED)


def estimate_tokens(text: str) -> int:
    """A rough token count for text, used before the provider reports the real one.

    About four characters per token for English prose; code and JSON run a
    little denser, so this rounds up. It only has to be the right order of
    magnitude: the daily budget has a margin, and the provider's own count
    replaces the estimate whenever it is reported.
    """
    return (len(text) + 2) // 3
