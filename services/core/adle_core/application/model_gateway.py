"""The one way a model request leaves Adle: through the quota, one at a time.

``generation.quota`` decides, ``generation.provider`` sends, and this module
joins them with the record of what was sent:

* a request goes to the provider the learner chose, and to no other;
* it is refused before it is sent if today's allowance for that provider is used up;
* if the last minute is full, it waits (cancellably) instead of failing;
* every request is written down before it is sent, so one that never returns
  still counts against the estimate;
* a rate-limit answer from the provider is waited out and tried once more,
  and only once;
* where a provider has several models and the one asked is away, or will not
  take the request made for it, the next in its list is asked in its place, and
  the caller is told (ADR-021).

Nothing else is retried here.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import select

from adle_core.errors import AdleError, NotFoundError
from adle_core.generation.provider import (
    ChatClient,
    ChatRequest,
    ChatResult,
    ModelSpec,
    NoModelAnsweredError,
    ProviderBadResponseError,
    ProviderConfig,
    ProviderError,
    ProviderKeyMissingError,
    ProviderModelUnavailableError,
    ProviderRateLimitedError,
    ProviderRequestRefusedError,
    ProviderUnavailableError,
    RequestCancelledError,
    Stage,
)
from adle_core.generation.quota import (
    QuotaLimits,
    UsageEntry,
    UsageSummary,
    Verdict,
    decide,
    estimate_tokens,
    summarise,
    tokens_for_characters,
)
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.orm import ModelUsage

logger = logging.getLogger(__name__)

#: How long to stand back after a rate-limit answer that does not say how long.
DEFAULT_RATE_LIMIT_PAUSE_SECONDS = 20.0
#: How long a model that did not answer is left alone before it is asked first again.
#: Long enough that one lesson does not keep finding out the same thing; short enough
#: that the model the learner was promised comes back the same evening.
MODEL_REST = timedelta(minutes=10)
#: Why the next model was asked: the model before it was away in one of three ways, or
#: it "refused" the request that was made for it.
PassedOver = Literal["failing", "gone", "silent", "refused"]
#: Usage older than this cannot matter to today's totals or to the last minute.
_LOOK_BACK = timedelta(hours=25)
_STEP_SECONDS = 0.25


class QuotaExhaustedError(AdleError):
    """Today's local allowance is used up. Nothing was sent."""

    status_code = 429
    code = "quota_exhausted"

    def __init__(self, resets_at: datetime | None, limit: str | None) -> None:
        super().__init__(
            "Today's allowance for AI requests is used up. Adle keeps its own count so that "
            "your key is never the one that runs out. The count starts again at midnight UTC.",
            detail={
                "resets_at": resets_at.isoformat() if resets_at else None,
                "limit": limit,
            },
        )


def _never_cancelled() -> bool:
    return False


class ModelGateway:
    """Requests to the provider in use, counted, and to its next model when one is away.

    Which provider is in use is the vault's to say (``CredentialVault.select``): it is
    the learner's choice and nothing here changes it. A provider's models are another
    matter. They are listed with the provider, in order, where the learner chooses it,
    and moving down that list keeps the request with the same provider, under the
    same key, at the same address.
    """

    def __init__(
        self,
        database: Database,
        clients: ChatClient | Sequence[ChatClient],
        *,
        limits: QuotaLimits | None = None,
        clock: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        several = (clients,) if isinstance(clients, ChatClient) else tuple(clients)
        if not several:
            raise ValueError("A gateway needs at least one provider.")
        self._clients = {client.config.provider_id: client for client in several}
        self._vault = several[0].vault
        if len(self._clients) != len(several) or any(
            client.vault is not self._vault for client in several
        ):
            raise ValueError("Providers need distinct names and one vault between them.")
        if self._vault.active_provider_id not in self._clients:
            self._vault.select(several[0].config.provider_id)
        self._database = database
        #: The same limits for every provider, when given (tests). Otherwise each its own.
        self._limits = limits
        self._clock = clock
        self._sleep = sleep
        # One request in flight, whoever asks.
        self._in_flight = threading.Lock()
        #: Models that did not answer, and until when each is passed over. Kept in memory
        #: only: after a restart every model is asked afresh.
        self._resting: dict[tuple[str, str], datetime] = {}

    # -- which provider -------------------------------------------------------

    def _client(self) -> ChatClient:
        return self._clients[self._vault.active_provider_id]

    @property
    def config(self) -> ProviderConfig:
        """The provider in use."""
        return self._client().config

    @property
    def providers(self) -> tuple[ProviderConfig, ...]:
        """Every provider that can be chosen, in the order they are offered."""
        return tuple(client.config for client in self._clients.values())

    @property
    def has_key(self) -> bool:
        """Whether the provider in use has a key."""
        return self._client().has_key

    def knows(self, provider_id: str) -> bool:
        return provider_id in self._clients

    def select(self, provider_id: str) -> None:
        """Use another provider from now on. Only ever called because the learner chose it."""
        if provider_id not in self._clients:
            raise NotFoundError("Adle does not know that AI provider.")
        self._vault.select(provider_id)
        logger.info("provider.selected provider=%s", provider_id)

    def limits_for(self, config: ProviderConfig) -> QuotaLimits:
        return self._limits or config.limits

    def usage(self) -> UsageSummary:
        """The local estimate of what has been used today at the provider in use.

        Not the provider's own count, and not shared between providers: each has its
        own allowance, so each is counted alone.
        """
        config = self.config
        return summarise(self._entries(config.provider_id), self._clock(), self.limits_for(config))

    # -- one request ----------------------------------------------------------

    def complete(
        self,
        request: ChatRequest,
        *,
        cancelled: Callable[[], bool] = _never_cancelled,
        on_wait: Callable[[float], None] | None = None,
        on_fallback: Callable[[str, str, PassedOver], None] | None = None,
        on_stage: Callable[[str, Stage], None] | None = None,
    ) -> ChatResult:
        """Send one request, or raise an ``AdleError`` that says why it was not answered.

        ``on_wait`` is told how many seconds a pause for the rate limit will last.
        ``on_fallback`` is told, by name, which model was passed over and which is being
        asked in its place, and why. ``on_stage`` is told, with the model's name, when it begins
        to think and when it begins to write. Raises ``RequestCancelledError`` if
        ``cancelled`` turns true while waiting or while the answer is arriving.

        The answer says which model wrote it (``model_name``) and, when that was not the
        provider's first, which one it stood in for (``instead_of``).
        """
        if not self.has_key:
            raise ProviderKeyMissingError
        prompt_tokens = estimate_tokens(request.system) + estimate_tokens(request.user)
        with self._in_flight:
            client = self._client()
            config = client.config
            models = self._models_to_ask(config)
            for position, spec in enumerate(models):
                try:
                    result = self._ask(
                        client, spec, request, prompt_tokens, cancelled, on_wait, on_stage
                    )
                except (ProviderModelUnavailableError, ProviderRequestRefusedError) as error:
                    if len(config.models) == 1:
                        # Nothing to move on to: the provider's own failure, as it always was.
                        raise
                    # A request is made for one model (``ModelSpec``). One that refuses it
                    # says nothing about whether the next, sent its own, will.
                    why: PassedOver = (
                        error.trouble
                        if isinstance(error, ProviderModelUnavailableError)
                        else "refused"
                    )
                    self._resting[(config.provider_id, spec.id)] = self._clock() + MODEL_REST
                    logger.info("provider.model_passed_over why=%s", why)
                    if position + 1 < len(models):
                        if on_fallback is not None:
                            on_fallback(spec.name, models[position + 1].name, why)
                        continue
                    raise NoModelAnsweredError(
                        config.display_name, [model.name for model in config.models]
                    ) from error
                self._resting.pop((config.provider_id, spec.id), None)
                first = config.models[0]
                return result if spec == first else replace(result, instead_of=first.name)
        raise AssertionError("a provider always has a model to ask")  # pragma: no cover

    # -- internals ---------------------------------------------------------

    def _models_to_ask(self, config: ProviderConfig) -> list[ModelSpec]:
        """The provider's models in order, without those that lately did not answer.

        When every one of them is resting, the one that has rested longest is asked,
        alone: a request should cost one attempt when nothing is known to work, and
        asking a different one each time finds the first to come back.
        """
        now = self._clock()
        until = {
            spec.id: self._resting.get((config.provider_id, spec.id)) for spec in config.models
        }
        rested = [spec for spec in config.models if (until[spec.id] or now) <= now]
        if rested:
            return rested
        return [min(config.models, key=lambda spec: until[spec.id] or now)]

    def _ask(
        self,
        client: ChatClient,
        spec: ModelSpec,
        request: ChatRequest,
        prompt_tokens: int,
        cancelled: Callable[[], bool],
        on_wait: Callable[[float], None] | None,
        on_stage: Callable[[str, Stage], None] | None = None,
    ) -> ChatResult:
        """One model, asked once; twice only if the provider said to slow down."""

        def stage_of_this_model(stage: Stage) -> None:
            if on_stage is not None:
                on_stage(spec.name, stage)

        # What this model may write, thinking included: the same bound the client sends.
        budget = max(request.max_output_tokens, spec.min_max_tokens)
        retried_after_rate_limit = False
        while True:
            self._wait_for_room(client.config, prompt_tokens + budget, cancelled, on_wait)
            usage_id = self._record_start(client.config, spec, request, prompt_tokens)
            try:
                result = client.complete(
                    request, model=spec, cancelled=cancelled, on_stage=stage_of_this_model
                )
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

    def _entries(self, provider_id: str) -> list[UsageEntry]:
        since = self._clock() - _LOOK_BACK
        with self._database.read() as session:
            rows = session.execute(
                select(
                    ModelUsage.started_at, ModelUsage.prompt_tokens, ModelUsage.completion_tokens
                ).where(ModelUsage.started_at >= since, ModelUsage.provider == provider_id)
            )
            return [
                UsageEntry(started_at=started_at, tokens=prompt + completion)
                for started_at, prompt, completion in rows
            ]

    def _wait_for_room(
        self,
        config: ProviderConfig,
        estimated_tokens: int,
        cancelled: Callable[[], bool],
        on_wait: Callable[[float], None] | None,
    ) -> None:
        while True:
            decision = decide(
                self._entries(config.provider_id),
                self._clock(),
                estimated_tokens=estimated_tokens,
                limits=self.limits_for(config),
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

    def _record_start(
        self, config: ProviderConfig, spec: ModelSpec, request: ChatRequest, prompt_tokens: int
    ) -> int:
        with self._database.session() as session:
            row = ModelUsage(
                started_at=self._clock(),
                provider=config.provider_id[:40],
                purpose=request.purpose[:40],
                model=spec.id[:100],
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
                # What it wrote and what it thought on the way: both were paid for.
                row.completion_tokens = estimate_tokens(result.text) + tokens_for_characters(
                    result.thinking_characters
                )
