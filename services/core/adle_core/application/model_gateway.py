"""The one way a model request leaves Adle: through the quota, one at a time per provider.

``generation.quota`` decides, ``generation.routing`` plans, ``generation.provider``
sends, and this module joins them with the record of what was sent:

* a request goes to a provider the learner chose, and to no other. That is one
  provider, or, if they let Adle choose ("automatic"), any provider they have given a
  key for: the one ``generation.routing`` plans for this kind of request, and the next
  in that plan if the first cannot answer (ADR-023);
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
import statistics
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
from adle_core.generation.routing import AUTOMATIC, Plan, Standing, plan
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.orm import ModelUsage

logger = logging.getLogger(__name__)

#: How long to stand back after a rate-limit answer that does not say how long.
DEFAULT_RATE_LIMIT_PAUSE_SECONDS = 20.0
#: How long a model that did not answer is left alone before it is asked first again.
#: Long enough that one lesson does not keep finding out the same thing; short enough
#: that the model the learner was promised comes back the same evening.
MODEL_REST = timedelta(minutes=10)
#: How long a provider that could not answer is asked second instead of first, when the
#: learner lets Adle use more than one.
PROVIDER_REST = timedelta(minutes=10)
#: The same when it is the learner's account there that is refusing (its key is not
#: accepted, or the provider answers with a notice about the account). Asking again in ten
#: minutes changes nothing and can cost one of a handful of tries: it is left alone until
#: its key is changed, a check of it succeeds, or this long has passed.
ACCOUNT_REST = timedelta(hours=6)
_ACCOUNT_TROUBLE: frozenset[str] = frozenset({"notice", "key_rejected"})
#: Why the next model, or the next provider, was asked. The first four are about one
#: model (ADR-021); the rest are about a whole provider (ADR-023).
PassedOver = Literal[
    "failing",
    "gone",
    "silent",
    "refused",
    "spent",
    "rate_limited",
    "notice",
    "key_rejected",
    "unreachable",
    "unreadable",
]
#: Usage older than this cannot matter to today's totals or to the last minute.
_LOOK_BACK = timedelta(hours=25)
_STEP_SECONDS = 0.25
#: How many of the latest answers of one kind say how long the next will take, and how
#: many there must be before they are believed over the provider's usual.
_MEASURED_FROM = 8
_MEASURED_AT_LEAST = 2


class QuotaExhaustedError(AdleError):
    """Today's local allowance is used up. Nothing was sent."""

    status_code = 429
    code = "quota_exhausted"

    def __init__(self, resets_at: datetime | None, limit: str | None) -> None:
        super().__init__(
            "Today’s AI allowance is used up. It resets at midnight UTC.",
            detail={
                "resets_at": resets_at.isoformat() if resets_at else None,
                "limit": limit,
            },
        )


def _never_cancelled() -> bool:
    return False


def _why(error: Exception) -> PassedOver:
    """Why a provider could not answer, as one of the reasons the interface has words for."""
    if isinstance(error, QuotaExhaustedError):
        return "spent"
    code = getattr(error, "code", "")
    if code == "provider_rate_limited":
        return "rate_limited"
    if code == "provider_notice":
        return "notice"
    if code == "provider_key_rejected":
        return "key_rejected"
    if code == "provider_request_refused":
        return "refused"
    if code == "provider_bad_response":
        return "unreadable"
    if isinstance(error, ProviderUnavailableError):
        return "failing" if error.provider_side else "unreachable"
    return "failing"


class ModelGateway:
    """Requests to the learner's providers, counted, each asked for what it is good at.

    Which providers may be asked is the vault's to say (``CredentialVault.select``): it
    is the learner's choice and nothing here changes it. If they chose one, every
    request goes there and nowhere else, whatever happens to it. If they chose
    "automatic", a request goes to the provider ``generation.routing`` plans for it
    among those they have given a key for, and to the next in the plan when the first
    cannot answer. A request never goes to a provider without a key of its own.

    A provider's models are another matter. They are listed with the provider, in
    order, where the learner sees it, and moving down that list keeps the request with
    the same provider, under the same key, at the same address (ADR-021).
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
        if self._vault.selection != AUTOMATIC and self._vault.selection not in self._clients:
            self._vault.select(AUTOMATIC)
        self._database = database
        #: The same limits for every provider, when given (tests). Otherwise each its own.
        self._limits = limits
        self._clock = clock
        self._sleep = sleep
        # One request in flight at each provider, whoever asks. Two providers are two
        # accounts with two allowances, so a short question to one does not have to wait
        # for a lesson that is being written at the other.
        self._in_flight = {name: threading.Lock() for name in self._clients}
        #: Models that did not answer, and until when each is passed over. Kept in memory
        #: only: after a restart every model is asked afresh.
        self._resting: dict[tuple[str, str], datetime] = {}
        #: Providers that could not answer, and until when each is asked second. Only
        #: matters when the learner lets Adle use more than one.
        self._providers_resting: dict[str, datetime] = {}
        #: Counts the keys each provider has had. What a request found out with one key
        #: is not remembered once there is another.
        self._key_changes = dict.fromkeys(self._clients, 0)

    # -- which provider -------------------------------------------------------

    @property
    def selection(self) -> str:
        """What the learner chose: one provider's name, or ``AUTOMATIC``."""
        return self._vault.selection

    @property
    def providers(self) -> tuple[ProviderConfig, ...]:
        """Every provider there is, in the order they are offered."""
        return tuple(client.config for client in self._clients.values())

    @property
    def config(self) -> ProviderConfig:
        """The provider a lesson would be asked of first, at this moment."""
        return self._clients[self.plan("lesson").provider_ids[0]].config

    @property
    def has_key(self) -> bool:
        """Whether anything can be asked at all, by the learner's choice."""
        return any(self._clients[name].has_key for name in self.plan("lesson").provider_ids)

    def knows(self, provider_id: str) -> bool:
        return provider_id in self._clients

    def has_key_for(self, provider_id: str) -> bool:
        """Whether this one provider has been given a key."""
        client = self._clients.get(provider_id)
        return client is not None and client.has_key

    def forget_trouble(self, provider_id: str) -> None:
        """Ask this provider first again. Its key has just been changed: what went wrong
        with the old one says nothing about the new one, including whatever a request
        that is still out with the old one comes back with."""
        if provider_id in self._key_changes:
            self._key_changes[provider_id] += 1
        self._providers_resting.pop(provider_id, None)

    def accepts(self, selection: str) -> bool:
        """Whether this is something the learner can choose: a provider, or automatic."""
        return selection == AUTOMATIC or selection in self._clients

    def select(self, selection: str) -> None:
        """Record the learner's choice. Only ever called because the learner made it."""
        if not self.accepts(selection):
            raise NotFoundError("Unknown AI provider.")
        self._vault.select(selection)
        logger.info("provider.selected selection=%s", selection)

    def limits_for(self, config: ProviderConfig) -> QuotaLimits:
        return self._limits or config.limits

    def usage(self, provider_id: str | None = None) -> UsageSummary:
        """The local estimate of what has been used today at one provider.

        Not the provider's own count, and not shared between providers: each has its
        own allowance, so each is counted alone. Without a name, the provider a lesson
        would go to first.
        """
        config = self._clients[provider_id].config if provider_id else self.config
        return summarise(self._entries(config.provider_id), self._clock(), self.limits_for(config))

    def standings(self) -> list[Standing]:
        """How each provider stands at this moment, for planning a request."""
        now = self._clock()
        found = []
        for client in self._clients.values():
            config = client.config
            limits = self.limits_for(config)
            entries = self._entries(config.provider_id)
            used = summarise(entries, now, limits)
            verdict = decide(entries, now, estimated_tokens=0, limits=limits)
            until = self._providers_resting.get(config.provider_id)
            found.append(
                Standing(
                    provider_id=config.provider_id,
                    name=config.display_name,
                    has_key=client.has_key,
                    first_for=config.first_for,
                    used=max(
                        used.requests_today / limits.requests_per_day,
                        used.tokens_today / limits.tokens_per_day,
                    ),
                    spent=verdict.verdict is Verdict.EXHAUSTED,
                    resting=until is not None and until > now,
                )
            )
        return found

    def plan(self, purpose: str) -> Plan:
        """Which providers a request of this kind would go to, in order, and why."""
        return plan(purpose, self._vault.selection, self.standings())

    def seconds_for(self, provider_id: str, purpose: str) -> tuple[int, bool]:
        """How long one answer of this kind takes at this provider, and whether measured.

        The middle of the last few that arrived on this computer, once there are a
        couple; before that, what is usual for the provider. Said to the learner as
        "about", never as a promise.
        """
        config = self._clients[provider_id].config
        with self._database.read() as session:
            recent = session.scalars(
                select(ModelUsage.seconds)
                .where(
                    ModelUsage.provider == provider_id,
                    ModelUsage.purpose == purpose,
                    ModelUsage.outcome == "ok",
                    ModelUsage.seconds >= 1.0,
                )
                .order_by(ModelUsage.id.desc())
                .limit(_MEASURED_FROM)
            ).all()
        taken = [float(seconds) for seconds in recent if seconds is not None]
        if len(taken) >= _MEASURED_AT_LEAST:
            return max(1, round(statistics.median(taken))), True
        return config.typical.of(purpose), False

    # -- one request ----------------------------------------------------------

    def complete(
        self,
        request: ChatRequest,
        *,
        cancelled: Callable[[], bool] = _never_cancelled,
        on_wait: Callable[[float], None] | None = None,
        on_fallback: Callable[[str, str, PassedOver], None] | None = None,
        on_stage: Callable[[str, Stage], None] | None = None,
        on_busy: Callable[[str], None] | None = None,
        provider_id: str | None = None,
        on_piece: Callable[[str], None] | None = None,
    ) -> ChatResult:
        """Send one request, or raise an ``AdleError`` that says why it was not answered.

        ``on_wait`` is told how many seconds a pause for the rate limit will last.
        ``on_fallback`` is told, by name, which model or provider was passed over and which
        is being asked in its place, and why. ``on_stage`` is told, with the model's name,
        when it begins to think and when it begins to write. ``on_busy`` is told a
        provider's name when the request has to wait for another one there to finish.
        Raises ``RequestCancelledError`` if ``cancelled`` turns true while waiting or
        while the answer is arriving.

        ``provider_id`` asks one provider and no other, whatever the learner's choice would
        plan: for checking that a key works.

        The answer says who wrote it (``provider_name``, ``model_name``) and, when that was
        not who was asked first, who it stood in for (``instead_of_provider``,
        ``instead_of``).
        """
        if provider_id is not None:
            if provider_id not in self._clients:
                raise NotFoundError("Unknown AI provider.")
            name = self._clients[provider_id].config.display_name
            route = Plan((provider_id,), (name,), automatic=False)
        else:
            route = self.plan(request.purpose)
        clients = [self._clients[name] for name in route.provider_ids]
        if not any(client.has_key for client in clients):
            raise ProviderKeyMissingError
        prompt_tokens = estimate_tokens(request.system) + estimate_tokens(request.user)
        for position, client in enumerate(clients):
            config = client.config
            key_at_start = self._key_changes[config.provider_id]
            try:
                self._take_turn(config, cancelled, on_busy)
                try:
                    result = self._ask_provider(
                        client,
                        request,
                        prompt_tokens,
                        cancelled,
                        on_wait,
                        on_fallback,
                        on_stage,
                        on_piece,
                    )
                finally:
                    self._in_flight[config.provider_id].release()
            except (ProviderError, QuotaExhaustedError) as error:
                why = _why(error)
                if why != "spent" and self._key_changes[config.provider_id] == key_at_start:
                    # Asked second for a while, not dropped: see ``routing``. Remembered
                    # whoever asked, so that a check of a key that failed is not followed
                    # by a question sent the same way.
                    rest = ACCOUNT_REST if why in _ACCOUNT_TROUBLE else PROVIDER_REST
                    self._providers_resting[config.provider_id] = self._clock() + rest
                following = clients[position + 1] if position + 1 < len(clients) else None
                # One provider by the learner's choice: its failure is the answer.
                if not route.automatic or following is None:
                    raise
                logger.info("provider.passed_over why=%s", why)
                if on_fallback is not None:
                    on_fallback(config.display_name, following.config.display_name, why)
                continue
            self._providers_resting.pop(config.provider_id, None)
            return replace(
                result,
                provider_name=config.display_name,
                instead_of_provider=clients[0].config.display_name if position else "",
            )
        raise AssertionError("a plan always has a provider to ask")  # pragma: no cover

    # -- internals ---------------------------------------------------------

    def _take_turn(
        self,
        config: ProviderConfig,
        cancelled: Callable[[], bool],
        on_busy: Callable[[str], None] | None,
    ) -> None:
        """Wait, cancellably, until nothing else is being asked of this provider."""
        lock = self._in_flight[config.provider_id]
        if lock.acquire(blocking=False):
            return
        if on_busy is not None:
            on_busy(config.display_name)
        while not lock.acquire(timeout=_STEP_SECONDS):
            if cancelled():
                raise RequestCancelledError
        if cancelled():
            lock.release()
            raise RequestCancelledError

    def _ask_provider(
        self,
        client: ChatClient,
        request: ChatRequest,
        prompt_tokens: int,
        cancelled: Callable[[], bool],
        on_wait: Callable[[float], None] | None,
        on_fallback: Callable[[str, str, PassedOver], None] | None,
        on_stage: Callable[[str, Stage], None] | None,
        on_piece: Callable[[str], None] | None = None,
    ) -> ChatResult:
        """One provider: its first model for this kind of request, or the next when that one
        is away (ADR-021, ADR-039)."""
        if not client.has_key:
            raise ProviderKeyMissingError
        config = client.config
        order = config.models_for(request.purpose)
        models = self._models_to_ask(config, order)
        for position, spec in enumerate(models):
            try:
                result = self._ask(
                    client, spec, request, prompt_tokens, cancelled, on_wait, on_stage, on_piece
                )
            except (ProviderModelUnavailableError, ProviderRequestRefusedError) as error:
                if len(order) == 1:
                    # Nothing to move on to: the provider's own failure, as it always was.
                    raise
                # A request is made for one model (``ModelSpec``). One that refuses it
                # says nothing about whether the next, sent its own, will.
                why: PassedOver = (
                    error.trouble if isinstance(error, ProviderModelUnavailableError) else "refused"
                )
                self._resting[(config.provider_id, spec.id)] = self._clock() + MODEL_REST
                logger.info("provider.model_passed_over why=%s", why)
                if position + 1 < len(models):
                    if on_fallback is not None:
                        on_fallback(spec.name, models[position + 1].name, why)
                    continue
                raise NoModelAnsweredError(
                    config.display_name, [model.name for model in order]
                ) from error
            self._resting.pop((config.provider_id, spec.id), None)
            first = order[0]
            return result if spec == first else replace(result, instead_of=first.name)
        raise AssertionError("a provider always has a model to ask")  # pragma: no cover

    def _models_to_ask(self, config: ProviderConfig, order: Sequence[ModelSpec]) -> list[ModelSpec]:
        """The models in ``order``, without those that lately did not answer.

        When every one of them is resting, the one that has rested longest is asked,
        alone: a request should cost one attempt when nothing is known to work, and
        asking a different one each time finds the first to come back.
        """
        now = self._clock()
        until = {spec.id: self._resting.get((config.provider_id, spec.id)) for spec in order}
        rested = [spec for spec in order if (until[spec.id] or now) <= now]
        if rested:
            return rested
        return [min(order, key=lambda spec: until[spec.id] or now)]

    def _ask(
        self,
        client: ChatClient,
        spec: ModelSpec,
        request: ChatRequest,
        prompt_tokens: int,
        cancelled: Callable[[], bool],
        on_wait: Callable[[float], None] | None,
        on_stage: Callable[[str, Stage], None] | None = None,
        on_piece: Callable[[str], None] | None = None,
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
            began = time.monotonic()
            try:
                result = client.complete(
                    request,
                    model=spec,
                    cancelled=cancelled,
                    on_stage=stage_of_this_model,
                    on_piece=on_piece,
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
                self._record_success(usage_id, prompt_tokens, result, time.monotonic() - began)
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

    def _record_success(
        self, usage_id: int, prompt_tokens: int, result: ChatResult, seconds: float
    ) -> None:
        with self._database.session() as session:
            row = session.get(ModelUsage, usage_id)
            if row is None:
                return
            row.outcome = "ok"
            row.seconds = round(max(0.0, seconds), 2)
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
