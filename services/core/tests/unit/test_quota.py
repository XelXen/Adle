"""The quota rules: pure decisions about whether a request may be sent now."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from adle_core.generation.quota import (
    DEFAULT_LIMITS,
    QuotaLimits,
    UsageEntry,
    Verdict,
    day_start,
    decide,
    estimate_tokens,
    next_reset,
    summarise,
)

NOON = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)


def at(seconds_ago: float, tokens: int = 1000) -> UsageEntry:
    return UsageEntry(started_at=NOON - timedelta(seconds=seconds_ago), tokens=tokens)


def test_the_defaults_are_the_documented_limits() -> None:
    # Documented for AIHubMix's free model: 5 requests a minute, 100 a day, 1,000,000 tokens
    # a day; kept to as they are, with no margin of Adle's under them (ADR-068).
    limits = DEFAULT_LIMITS
    assert (limits.requests_per_minute, limits.requests_per_day, limits.tokens_per_day) == (
        5,
        100,
        1_000_000,
    )


def test_a_day_with_no_limit_is_never_used_up() -> None:
    # NVIDIA's: 40 a minute, and none a day (ADR-068).
    limits = QuotaLimits(requests_per_minute=40, requests_per_day=None, tokens_per_day=None)
    busy_day = [at(3600 + second, tokens=500_000) for second in range(1000)]
    decision = decide(busy_day, NOON, estimated_tokens=900_000, limits=limits)
    assert decision.verdict is Verdict.ALLOWED
    summary = summarise(busy_day, NOON, limits)
    assert (summary.requests_today, summary.tokens_today) == (1000, 500_000_000)


def test_a_minute_still_counts_where_the_day_does_not() -> None:
    limits = QuotaLimits(requests_per_minute=40, requests_per_day=None, tokens_per_day=None)
    entries = [at(59 - second * 1.4) for second in range(40)]
    decision = decide(entries, NOON, estimated_tokens=10, limits=limits)
    assert decision.verdict is Verdict.WAIT
    assert decision.wait_seconds == pytest.approx(1.0)


def test_a_limit_is_at_least_one() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        QuotaLimits(requests_per_minute=0)
    with pytest.raises(ValueError, match="at least 1"):
        QuotaLimits(requests_per_day=0, tokens_per_day=None)
    QuotaLimits(requests_per_minute=1, requests_per_day=None, tokens_per_day=None)


def test_a_first_request_is_allowed() -> None:
    assert decide([], NOON, estimated_tokens=5000).verdict is Verdict.ALLOWED


def test_requests_within_the_minute_allowance_go_straight_through() -> None:
    entries = [at(50), at(30), at(5)]
    assert decide(entries, NOON, estimated_tokens=1000).verdict is Verdict.ALLOWED


def test_a_full_minute_means_waiting_only_until_the_oldest_request_leaves_it() -> None:
    entries = [at(50), at(30), at(20), at(10), at(5)]
    decision = decide(entries, NOON, estimated_tokens=1000)
    assert decision.verdict is Verdict.WAIT
    assert decision.wait_seconds == pytest.approx(10.0)
    # Once that time has passed, the request is allowed.
    later = NOON + timedelta(seconds=decision.wait_seconds)
    assert decide(entries, later, estimated_tokens=1000).verdict is Verdict.ALLOWED


def test_with_more_than_a_window_of_recent_requests_the_wait_covers_enough_of_them() -> None:
    # Seven in the last minute against a limit of five: three of them have to leave it.
    entries = [at(55), at(50), at(40), at(30), at(20), at(10), at(5)]
    decision = decide(entries, NOON, estimated_tokens=1000)
    assert decision.verdict is Verdict.WAIT
    assert decision.wait_seconds == pytest.approx(20.0)
    later = NOON + timedelta(seconds=decision.wait_seconds)
    assert decide(entries, later, estimated_tokens=1000).verdict is Verdict.ALLOWED


def test_requests_older_than_a_minute_do_not_count_against_the_minute() -> None:
    entries = [at(61), at(120), at(300), at(600)]
    assert decide(entries, NOON, estimated_tokens=1000).verdict is Verdict.ALLOWED


def test_the_daily_request_allowance_ends_the_day() -> None:
    limits = QuotaLimits(requests_per_minute=4, requests_per_day=3, tokens_per_day=900_000)
    entries = [at(3600), at(7200), at(9000)]
    decision = decide(entries, NOON, estimated_tokens=10, limits=limits)
    assert decision.verdict is Verdict.EXHAUSTED
    assert decision.exhausted == "requests"
    assert decision.resets_at == datetime(2026, 11, 20, tzinfo=UTC)


def test_the_daily_token_allowance_counts_the_request_about_to_be_sent() -> None:
    limits = QuotaLimits(requests_per_minute=4, requests_per_day=90, tokens_per_day=10_000)
    entries = [at(3600, tokens=6000), at(7200, tokens=3000)]
    assert decide(entries, NOON, estimated_tokens=1000, limits=limits).verdict is Verdict.ALLOWED
    decision = decide(entries, NOON, estimated_tokens=1001, limits=limits)
    assert (decision.verdict, decision.exhausted) == (Verdict.EXHAUSTED, "tokens")


def test_yesterdays_requests_do_not_count_against_today() -> None:
    limits = QuotaLimits(requests_per_minute=4, requests_per_day=2, tokens_per_day=5000)
    yesterday = [
        UsageEntry(datetime(2026, 11, 18, 23, 0, tzinfo=UTC), tokens=4000),
        UsageEntry(datetime(2026, 11, 18, 22, 0, tzinfo=UTC), tokens=4000),
    ]
    assert decide(yesterday, NOON, estimated_tokens=1000, limits=limits).verdict is Verdict.ALLOWED
    summary = summarise(yesterday, NOON, limits)
    assert (summary.requests_today, summary.tokens_today) == (0, 0)


def test_the_minute_window_runs_across_midnight() -> None:
    just_after = datetime(2026, 11, 20, 0, 0, 10, tzinfo=UTC)
    entries = [
        UsageEntry(just_after - timedelta(seconds=seconds), tokens=10)
        for seconds in (20, 25, 30, 40, 45)
    ]
    decision = decide(entries, just_after, estimated_tokens=10)
    # None of them counts against the new day, all of them against the last minute.
    assert decision.verdict is Verdict.WAIT
    assert summarise(entries, just_after).requests_today == 0
    assert summarise(entries, just_after).requests_last_minute == 5


def test_the_day_is_counted_in_utc_whatever_zone_the_clock_is_in() -> None:
    tokyo = datetime(2026, 11, 20, 8, 30, tzinfo=UTC).astimezone()
    assert day_start(tokyo) == datetime(2026, 11, 20, tzinfo=UTC)
    assert next_reset(tokyo) == datetime(2026, 11, 21, tzinfo=UTC)


def test_the_summary_reports_what_was_used_and_when_it_resets() -> None:
    summary = summarise([at(10, tokens=1200), at(400, tokens=800)], NOON)
    assert summary.requests_today == 2
    assert summary.tokens_today == 2000
    assert summary.requests_last_minute == 1
    assert summary.resets_at == datetime(2026, 11, 20, tzinfo=UTC)
    assert summary.limits is DEFAULT_LIMITS


def test_limits_must_be_positive() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        QuotaLimits(requests_per_minute=0)


def test_the_token_estimate_errs_on_the_high_side() -> None:
    assert estimate_tokens("") == 0
    prose = "The neuron multiplies every input by its weight and adds the results together. " * 20
    # About four characters to a token in English; the estimate must not be lower than that.
    assert estimate_tokens(prose) >= len(prose) // 4
    assert estimate_tokens(prose) <= len(prose) // 2


@given(
    seconds_ago=st.lists(st.floats(min_value=0, max_value=86_400 * 2), max_size=120),
    per_minute=st.integers(min_value=1, max_value=6),
)
def test_waiting_as_long_as_asked_always_opens_the_minute_window(
    seconds_ago: list[float], per_minute: int
) -> None:
    limits = QuotaLimits(
        requests_per_minute=per_minute, requests_per_day=100_000, tokens_per_day=10**12
    )
    entries = [at(value, tokens=1) for value in seconds_ago]
    decision = decide(entries, NOON, estimated_tokens=1, limits=limits)
    assert decision.verdict in (Verdict.ALLOWED, Verdict.WAIT)
    if decision.verdict is Verdict.WAIT:
        assert 0 <= decision.wait_seconds <= 60
        later = NOON + timedelta(seconds=decision.wait_seconds, microseconds=1)
        assert decide(entries, later, estimated_tokens=1, limits=limits).verdict is Verdict.ALLOWED
