"""The one way a model request leaves Adle: through the quota, one at a time.

``generation.quota`` decides, ``generation.provider`` sends, and this module
joins them with the record of what was sent:

* a request is refused before it is sent if today's allowance is used up;
* if the last minute is full, it waits (cancellably) instead of failing;
* every request is written down before it is sent, so one that never returns
  still counts against the estimate;
* a rate-limit answer from the provider is waited out and tried once more,
  and only once. Nothing else is retried here.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import select

from adle_core.errors import AdleError
from adle_core.generation.provider import (
    ChatClient,
    ChatRequest,
    ChatResult,
    ProviderBadResponseError,
    ProviderConfig,
    ProviderError,
    ProviderKeyMissingError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    RequestCancelledError,
)
from adle_core.generation.quota import (
    DEFAULT_LIMITS,
    QuotaLimits,
    UsageEntry,
    UsageSummary,
    Verdict,
    decide,
    estimate_tokens,
    summarise,
)
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.orm import ModelUsage

logger = logging.getLogger(__name__)

#: How long to stand back after a rate-limit answer that does not say how long.
DEFAULT_RATE_LIMIT_PAUSE_SECONDS = 20.0
#: Usage older than this cannot matter to today's totals or to the last minute.
_LOOK_BACK = timedelta(hours=25)
_STEP_SECONDS = 0.25


class QuotaExhaustedError(AdleError):
    """Today's local allowance is used up. Nothing was sent."""

    status_code = 429
    code = "quota_exhausted"

    def __init__(self, resets_at: datetime | None, limit: str | None) -> None:
        super().__init__(
            "Today's allowance for AI requests is used up. Adle keeps its own count a little "
            "below the provider's limit so that your key is never the one that runs out. "
            "The count starts again at midnight UTC.",
            detail={
                "resets_at": resets_at.isoformat() if resets_at else None,
                "limit": limit,
            },
        )


def _never_cancelled() -> bool:
    return False


class ModelGateway:
    def __init__(
        self,
        database: Database,
        client: ChatClient,
        *,
        limits: QuotaLimits = DEFAULT_LIMITS,
        clock: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._database = database
        self._client = client
        self._limits = limits
        self._clock = clock
        self._sleep = sleep
        # One request in flight, whoever asks.
        self._in_flight = threading.Lock()

    @property
    def config(self) -> ProviderConfig:
        return self._client.config

    @property
    def has_key(self) -> bool:
        return self._client.has_key

    def usage(self) -> UsageSummary:
        """The local estimate of what has been used today. Not the provider's own count."""
        return summarise(self._entries(), self._clock(), self._limits)

    def complete(
        self,
        request: ChatRequest,
        *,
        cancelled: Callable[[], bool] = _never_cancelled,
        on_wait: Callable[[float], None] | None = None,
    ) -> ChatResult:
        """Send one request, or raise an ``AdleError`` that says why it was not answered.

        ``on_wait`` is told how many seconds a pause for the rate limit will last.
        Raises ``RequestCancelledError`` if ``cancelled`` turns true while waiting
        or while the answer is arriving.
        """
        if not self._client.has_key:
            raise ProviderKeyMissingError
        prompt_tokens = estimate_tokens(request.system) + estimate_tokens(request.user)
        with self._in_flight:
            retried_after_rate_limit = False
            while True:
                self._wait_for_room(prompt_tokens + request.max_output_tokens, cancelled, on_wait)
                usage_id = self._record_start(request, prompt_tokens)
                try:
                    result = self._client.complete(request, cancelled=cancelled)
                except ProviderRateLimitedError as error:
                    self._record_end(usage_id, "rate_limited")
                    if retried_after_rate_limit:
                        raise
                    retried_after_rate_limit = True
                    pause = error.retry_after_seconds
                    self._pause(
                        DEFAULT_RATE_LIMIT_PAUSE_SECONDS if pause is None else pause,
                        cancelled,
                        on_wait,
                    )
                except RequestCancelledError:
                    self._record_end(usage_id, "cancelled")
                    raise
                except ProviderUnavailableError:
                    self._record_end(usage_id, "unavailable")
                    raise
                except ProviderBadResponseError:
                    self._record_end(usage_id, "unreadable")
                    raise
                except ProviderError:
                    self._record_end(usage_id, "refused")
                    raise
                else:
                    self._record_success(usage_id, prompt_tokens, result)
                    return result

    # -- internals ---------------------------------------------------------

    def _entries(self) -> list[UsageEntry]:
        since = self._clock() - _LOOK_BACK
        with self._database.session() as session:
            rows = session.execute(
                select(
                    ModelUsage.started_at, ModelUsage.prompt_tokens, ModelUsage.completion_tokens
                ).where(ModelUsage.started_at >= since)
            )
            return [
                UsageEntry(started_at=started_at, tokens=prompt + completion)
                for started_at, prompt, completion in rows
            ]

    def _wait_for_room(
        self,
        estimated_tokens: int,
        cancelled: Callable[[], bool],
        on_wait: Callable[[float], None] | None,
    ) -> None:
        while True:
            decision = decide(
                self._entries(),
                self._clock(),
                estimated_tokens=estimated_tokens,
                limits=self._limits,
            )
            if decision.verdict is Verdict.ALLOWED:
                return
            if decision.verdict is Verdict.EXHAUSTED:
                logger.info("quota.exhausted limit=%s", decision.exhausted)
                raise QuotaExhaustedError(decision.resets_at, decision.exhausted)
            self._pause(decision.wait_seconds, cancelled, on_wait)

    def _pause(
        self,
        seconds: float,
        cancelled: Callable[[], bool],
        on_wait: Callable[[float], None] | None,
    ) -> None:
        if on_wait is not None:
            on_wait(seconds)
        # A hair more than asked, so the window is certainly open afterwards.
        remaining = seconds + 0.05
        while remaining > 0:
            if cancelled():
                raise RequestCancelledError
            step = min(_STEP_SECONDS, remaining)
            self._sleep(step)
            remaining -= step
        if cancelled():
            raise RequestCancelledError

    def _record_start(self, request: ChatRequest, prompt_tokens: int) -> int:
        with self._database.session() as session:
            row = ModelUsage(
                started_at=self._clock(),
                purpose=request.purpose[:40],
                model=self._client.config.model[:100],
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                estimated=True,
                outcome="pending",
            )
            session.add(row)
            session.flush()
            return row.id

    def _record_end(self, usage_id: int, outcome: str) -> None:
        with self._database.session() as session:
            row = session.get(ModelUsage, usage_id)
            if row is not None:
                row.outcome = outcome

    def _record_success(self, usage_id: int, prompt_tokens: int, result: ChatResult) -> None:
        with self._database.session() as session:
            row = session.get(ModelUsage, usage_id)
            if row is None:
                return
            row.outcome = "ok"
            if result.usage_reported:
                row.prompt_tokens = result.prompt_tokens
                row.completion_tokens = result.completion_tokens
                row.estimated = False
            else:
                row.prompt_tokens = prompt_tokens
                row.completion_tokens = estimate_tokens(result.text)
