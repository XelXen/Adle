"""The model provider: one OpenAI-compatible chat completion at a time.

This is the only module that sends anything off the computer. It knows which
providers exist, how to make one request to one of them, and how to read one
answer; deciding *whether* a request may be sent (quota), *which* model of a
provider to ask (the gateway), *what* to ask (prompts), and what to do with the
answer (validation) all happen elsewhere.

Rules that hold here:

* The key is read from the vault for each request and placed in one header.
  It is never logged, stored, or put in an error message. A client is bound to
  one provider and asks the vault for that provider's key and no other, so a
  key cannot reach an address it was not given for.
* Requests go only to the configured base URL. Redirects are not followed, and
  proxy or credential settings from the environment are not used.
* Only fields a model's own API reference lists are sent to it.
* Nothing from a request or a response body is logged. Errors carry a status
  code and a fixed sentence.
* A response is bounded in size and in time, and is given up the moment the
  learner cancels: whoever asked is told at once, and the connection is closed
  as soon as it next says anything (or its time runs out).
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import queue
import re
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx2 as httpx

from adle_core.errors import AdleError
from adle_core.generation.credentials import DEFAULT_PROVIDER_ID, CredentialVault
from adle_core.generation.quota import DEFAULT_LIMITS, QuotaLimits
from adle_core.generation.routing import PURPOSES

logger = logging.getLogger(__name__)

BASE_URL_ENV = "ADLE_PROVIDER_BASE_URL"
MODEL_ENV = "ADLE_PROVIDER_MODEL"
#: Development and tests: other addresses for the known providers, as a JSON object
#: from provider id to base URL. Each stays the provider it was, and says where it goes.
ENDPOINTS_ENV = "ADLE_PROVIDER_ENDPOINTS"

DEFAULT_BASE_URL = "https://aihubmix.com/v1"
DEFAULT_MODEL = "coding-kimi-k3-free"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

#: An answer longer than this is not a lesson; it is a model that did not stop.
MAX_RESPONSE_CHARACTERS = 400_000
#: Everything a streamed answer may send, wrappers and thinking included. A long lesson
#: arrives as some ten thousand small events of a few hundred characters each.
MAX_STREAM_CHARACTERS = 48_000_000
#: One line of a stream. An event carries a few words of the answer; nothing honest is longer.
MAX_LINE_CHARACTERS = 1_000_000
#: Upper bound honoured for a ``Retry-After`` header.
MAX_RETRY_AFTER_SECONDS = 90.0


class ProviderConfigError(ValueError):
    """The provider settings are not something Adle will send data to."""


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """One model at a provider, and what its own API reference says it accepts.

    Only documented fields are sent to a model. An endpoint that validates its input may
    refuse a field it does not list, and one that ignores it today may not tomorrow.
    """

    #: As the provider names it in a request.
    id: str
    #: As a person would name it.
    name: str
    #: The reference lists ``stream_options``: token counts can be asked for at the end
    #: of a stream. Without it the counts are estimated here.
    usage_option: bool = False
    #: The reference lists ``response_format``: a single JSON object can be asked for.
    #: Without it the prompt asks, and the answer is read leniently.
    json_mode: bool = False
    #: The least to ask for as ``max_tokens``. A model that reasons before it answers
    #: counts the reasoning in it, and a small budget ends before the answer begins.
    min_max_tokens: int = 0
    #: Sent as ``reasoning_effort``, a field the model's reference lists. ``None`` sends
    #: nothing and leaves the model at its provider's default. Try a value against the
    #: real endpoint before relying on it: see the notes on NVIDIA's models below.
    reasoning_effort: str | None = None
    #: The same, for one kind of request only (``purpose``, value), where it was measured
    #: to help that kind and not the others. Takes the place of ``reasoning_effort``.
    reasoning_for: tuple[tuple[str, str], ...] = ()
    #: The reference lists pictures as part of a message, and the real endpoint was seen
    #: to read one: only such a model is sent a picture of a page (ADR-060).
    images: bool = False

    def effort(self, purpose: str) -> str | None:
        """What is sent as ``reasoning_effort`` for this kind of request, if anything."""
        return dict(self.reasoning_for).get(purpose, self.reasoning_effort)


AIHUBMIX_MODEL = ModelSpec(
    id=DEFAULT_MODEL, name="Coding Kimi K3 (free)", usage_option=True, json_mode=True
)

#: NVIDIA's models (ADR-021, ADR-039). Each entry follows that model's page under
#: https://build.nvidia.com/, and then what the endpoint was seen to do, which is not
#: always what the page says. Which of them is asked for what is ``NVIDIA_ORDERS``, from
#: one run of each kind of request on 2026-11-21 (PERFORMANCE.md). The two Nemotron models
#: are sent nothing but the fields every request has, but for the one below that was
#: measured against the endpoint: Nemotron 3 Ultra thinks less for a lesson (ADR-048).
NEMOTRON_ULTRA = ModelSpec(
    id="nvidia/nemotron-3-ultra-550b-a55b",
    name="Nemotron 3 Ultra",
    # The reference lists "none", "medium" and "high" (the default). A lesson's words at
    # "high" took 116 to 232 s, the model thinking 18,000 to 35,000 characters first; at
    # "medium" 53 to 74 s, thinking 1,500 to 3,300, and as correct: three lessons of three
    # usable at their first answer, every figure drawn (2026-11-22, ADR-048).
    # Asked for a lesson as a slideshow (ADR-049), the model thought 19,000 to 59,000
    # characters at "medium", and a lesson could be begun only after 118 to 313 s; at
    # "none", after 13.5 s, whole at 63 s. What thinking had caught (a wrong option that is
    # the right one written another way, a key its own working does not reach) is caught
    # in drafts now, and the prompt asks for the working before the answer (ADR-049).
    # A course plan was no quicker at "medium" (62 s, against 18 to 52), so it is left at
    # the default.
    reasoning_for=(("lesson", "none"),),
)
NEMOTRON_SUPER = ModelSpec(
    id="nvidia/nemotron-3.5-super-vl-120b-a12b",
    name="Nemotron 3.5 Super",
    # Its reference takes a picture as a part of the message ("image_url", a data URL).
    # On 2026-11-24 it read a typed page and a handwritten one word for word, the drawing
    # described in a line, a PNG of 110 to 190 KB each, in 2 to 16 s (ADR-060).
    images=True,
)
NVIDIA_MODELS = (
    NEMOTRON_ULTRA,
    NEMOTRON_SUPER,
    ModelSpec(
        id="moonshotai/kimi-k3.1-pro",
        name="Kimi K3.1 Pro",
        usage_option=True,
        min_max_tokens=16_384,
        # The reference gives "low" as the default, and the request it shows sends it.
        # Left out, the model was seen to think for more than eight minutes over one
        # lesson without beginning to write; sent, it began after one and a half and had
        # written the lesson in five.
        reasoning_effort="low",
    ),
    ModelSpec(
        id="mistralai/mistral-large-4-1t-a52b",
        name="Mistral Large 4",
        min_max_tokens=16_384,
        # The one place Adle sends something a reference does not list, and why. The
        # reference lists the field with the values "none" and "high", and "none" as what
        # leaving it out means. On 2026-11-20 the endpoint refused "none" (HTTP 400);
        # left out, the model thought for eight minutes over one lesson without writing;
        # with "low" it wrote the lesson in seven and a half. If the endpoint ever
        # refuses "low" too, the gateway moves on to the next model and says so.
        reasoning_effort="low",
    ),
)

_ULTRA, _SUPER, _KIMI, _MISTRAL = (spec.id for spec in NVIDIA_MODELS)
#: For each kind of request, NVIDIA's models in the order they are asked (ADR-039): the one
#: measured to do it well and soonest first, then those that stand in. Measured on
#: 2026-11-21: a question in 7 s (Super) and 8 s (Ultra) against 66 s (Kimi); suggested
#: concepts in 30 s (Ultra), 39 s (Super), 123 s (Kimi); a lesson in 113 s (Ultra) against
#: 254 s (Kimi), Super's twice not usable; a scene file in 20 s (Ultra) and 134 s (Kimi),
#: Super's empty. Kimi, a model for code, draws the pictures; everything else is written by
#: a model that does not keep the learner waiting.
NVIDIA_ORDERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ask", (_SUPER, _ULTRA, _KIMI)),
    ("check", (_SUPER, _ULTRA)),
    ("curriculum", (_ULTRA, _SUPER, _KIMI, _MISTRAL)),
    ("lesson", (_ULTRA, _KIMI, _MISTRAL)),
    ("scene", (_KIMI, _ULTRA)),
    # The one model whose reading of a picture was seen (ADR-060). Mistral Large 4's
    # reference takes pictures too; it is not asked until it has been tried by hand.
    ("read", (_SUPER,)),
)

#: Adle's own caution for a provider that publishes no daily limit for these models.
#: It is there so that a mistake cannot run away with an account, not to ration lessons.
NVIDIA_LIMITS = QuotaLimits(requests_per_minute=4, requests_per_day=200, tokens_per_day=3_000_000)


@dataclass(frozen=True, slots=True)
class TypicalSeconds:
    """How long one answer of each kind usually takes at a provider.

    Used to tell the learner what to expect before Adle has measured anything on this
    computer. Once a few answers have arrived, what was measured is used instead
    (``ModelGateway.seconds_for``).
    """

    lesson: int = 60
    scene: int = 45
    curriculum: int = 30
    ask: int = 15
    check: int = 8
    #: One page read from its picture.
    read: int = 10

    def of(self, purpose: str) -> int:
        found = getattr(self, purpose, None)
        return found if isinstance(found, int) else self.lesson


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider_id: str = DEFAULT_PROVIDER_ID
    display_name: str = "AIHubMix"
    base_url: str = DEFAULT_BASE_URL
    #: In the order they are tried. The first is the one used; a later one is asked only
    #: when the ones before it are not available (see ``ModelGateway``).
    models: tuple[ModelSpec, ...] = (AIHUBMIX_MODEL,)
    #: For a kind of request, the ids of the models to ask instead, in order (ADR-039).
    #: A kind not listed asks ``models`` in their order.
    orders: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: What this provider is asked first for when the learner lets Adle use every provider
    #: they have a key for (``generation.routing``, ADR-039). Anything else goes first to
    #: another provider, and here after it.
    first_for: frozenset[str] = frozenset(PURPOSES)
    limits: QuotaLimits = DEFAULT_LIMITS
    #: True when ``limits`` sit just under limits the provider publishes; False when they
    #: are only Adle's own caution. The interface says which.
    limits_published: bool = True
    #: What to expect of it before anything has been measured here.
    typical: TypicalSeconds = TypicalSeconds()
    connect_timeout_seconds: float = 15.0
    #: The longest silence tolerated while an answer is arriving.
    read_timeout_seconds: float = 120.0
    #: The longest one request may take in all.
    total_timeout_seconds: float = 420.0

    def __post_init__(self) -> None:
        if not self.models:
            raise ProviderConfigError("A provider needs at least one model.")
        known = {spec.id for spec in self.models}
        for purpose, ids in self.orders:
            if purpose not in PURPOSES or not ids or not set(ids) <= known:
                raise ProviderConfigError(
                    f"The order of models for {purpose!r} must name this provider's models."
                )
        if not self.first_for <= set(PURPOSES):
            raise ProviderConfigError("A provider can be asked first only for known requests.")

    @property
    def model(self) -> str:
        """The model used unless it is unavailable."""
        return self.models[0].id

    def models_for(self, purpose: str) -> tuple[ModelSpec, ...]:
        """The models to ask for a kind of request, in order: its own order, or all of them.

        Reading a picture asks only models that see pictures: none, at a provider without one.
        """
        found = self.models
        for listed, ids in self.orders:
            if listed == purpose:
                by_id = {spec.id: spec for spec in self.models}
                found = tuple(by_id[model_id] for model_id in ids)
                break
        if purpose == "read":
            return tuple(spec for spec in found if spec.images)
        return found

    def serves(self, purpose: str) -> bool:
        """Whether this provider has a model for this kind of request at all."""
        return bool(self.models_for(purpose))

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]) -> ProviderConfig:
        """Developer configuration: another endpoint or model, set before launch.

        An endpoint other than the default is named as such everywhere the
        provider is shown, so data never goes somewhere the learner was not told.
        """
        base_url = environ.get(BASE_URL_ENV, "").strip() or DEFAULT_BASE_URL
        model = environ.get(MODEL_ENV, "").strip() or DEFAULT_MODEL
        host = check_base_url(base_url)
        if not model or len(model) > 100 or any(character.isspace() for character in model):
            raise ProviderConfigError(f"{MODEL_ENV} is not a usable model name.")
        models = (
            (AIHUBMIX_MODEL,)
            if model == DEFAULT_MODEL
            else (ModelSpec(id=model, name=model, usage_option=True, json_mode=True),)
        )
        if base_url.rstrip("/") == DEFAULT_BASE_URL:
            return cls(base_url=DEFAULT_BASE_URL, models=models)
        return cls(
            provider_id="custom",
            display_name=f"Custom endpoint ({host})",
            base_url=base_url.rstrip("/"),
            models=models,
        )


#: AIHubMix's one model is made for code. With another provider to write the rest, it
#: draws the pictures, and its small daily allowance goes on them alone (ADR-039).
AIHUBMIX = ProviderConfig(first_for=frozenset({"scene"}))
NVIDIA = ProviderConfig(
    provider_id="nvidia",
    display_name="NVIDIA NIM",
    base_url=NVIDIA_BASE_URL,
    models=NVIDIA_MODELS,
    orders=NVIDIA_ORDERS,
    first_for=frozenset(PURPOSES) - {"scene"},
    limits=NVIDIA_LIMITS,
    limits_published=False,
    # With each kind of request at the model that does it soonest (ADR-039), as measured
    # on 2026-11-21: a lesson's text in about two minutes, a picture in two to three, a
    # list of concepts in half a minute, an answer in ten seconds.
    typical=TypicalSeconds(lesson=120, scene=150, curriculum=35, ask=10, check=10, read=8),
    # These models think before they answer, and the shared endpoints queue: a small
    # question took forty seconds to begin to be answered when this was written.
    read_timeout_seconds=180.0,
    total_timeout_seconds=900.0,
)


@dataclass(frozen=True, slots=True)
class ProviderCatalogue:
    """The providers this installation can use.

    The learner chooses one, or lets Adle use every one they have given a key for
    (ADR-023). Nothing else decides.
    """

    providers: tuple[ProviderConfig, ...] = (AIHUBMIX, NVIDIA)

    def __post_init__(self) -> None:
        ids = [provider.provider_id for provider in self.providers]
        if not ids or len(set(ids)) != len(ids):
            raise ProviderConfigError("Providers need distinct names, and there must be one.")

    @property
    def default(self) -> ProviderConfig:
        return self.providers[0]

    def get(self, provider_id: str) -> ProviderConfig | None:
        return next((item for item in self.providers if item.provider_id == provider_id), None)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]) -> ProviderCatalogue:
        """The known providers, or what a developer set in their place before launch.

        ``ADLE_PROVIDER_BASE_URL`` (or ``ADLE_PROVIDER_MODEL``) replaces them all with
        one endpoint, as it always has. ``ADLE_PROVIDER_ENDPOINTS`` keeps the known
        providers and moves some of them to other addresses; each then carries the
        address in its name, so it is never silently somewhere else.
        """
        if environ.get(BASE_URL_ENV, "").strip() or environ.get(MODEL_ENV, "").strip():
            return cls(providers=(ProviderConfig.from_environment(environ),))
        raw = environ.get(ENDPOINTS_ENV, "").strip()
        if not raw:
            return cls()
        try:
            moved = json.loads(raw)
        except ValueError as error:
            raise ProviderConfigError(f"{ENDPOINTS_ENV} is not valid JSON.") from error
        known = {provider.provider_id for provider in cls().providers}
        if not isinstance(moved, dict) or not set(moved) <= known:
            raise ProviderConfigError(
                f"{ENDPOINTS_ENV} must map known provider names ({', '.join(sorted(known))}) "
                "to addresses."
            )
        providers = []
        for provider in cls().providers:
            base_url = moved.get(provider.provider_id)
            if base_url is None:
                providers.append(provider)
                continue
            if not isinstance(base_url, str):
                raise ProviderConfigError(f"{ENDPOINTS_ENV} must map names to addresses.")
            host = check_base_url(base_url)
            providers.append(
                replace(
                    provider,
                    base_url=base_url.rstrip("/"),
                    display_name=f"{provider.display_name} (custom endpoint {host})",
                )
            )
        return cls(providers=tuple(providers))


def check_base_url(base_url: str) -> str:
    """Return the host of an acceptable base URL, or raise ``ProviderConfigError``.

    Only HTTPS is accepted, except for a server on this computer (a local
    model, or the fake provider used in tests).
    """
    try:
        parts = urlsplit(base_url)
        host = parts.hostname or ""
    except ValueError as error:
        raise ProviderConfigError(f"{BASE_URL_ENV} is not a valid address.") from error
    if parts.username or parts.password or parts.query or parts.fragment or not host:
        raise ProviderConfigError(f"{BASE_URL_ENV} must be a plain address without credentials.")
    if parts.scheme == "https" or (parts.scheme == "http" and host in _LOOPBACK_HOSTS):
        return host
    raise ProviderConfigError(
        f"{BASE_URL_ENV} must use https (http is accepted only for this computer)."
    )


# -- errors ---------------------------------------------------------------------


class ProviderError(AdleError):
    """Something went wrong between Adle and the provider. Recoverable by trying again later."""

    status_code = 502
    code = "provider_error"


class ProviderKeyMissingError(ProviderError):
    status_code = 409
    code = "provider_key_missing"

    def __init__(self) -> None:
        super().__init__("Add your AI provider key in Settings to use this.")


class PicturesUnreadableError(ProviderError):
    """No provider the learner chose has a model that reads pictures (ADR-060)."""

    status_code = 409
    code = "pictures_unreadable"

    def __init__(self, names: tuple[str, ...] = ()) -> None:
        who = " or ".join(names) if names else "Your AI provider"
        super().__init__(
            f"{who} can’t read pictures of pages. Add a key for NVIDIA NIM in Settings to "
            "have them read."
        )


class ProviderKeyRejectedError(ProviderError):
    status_code = 409
    code = "provider_key_rejected"

    def __init__(self) -> None:
        super().__init__("The AI provider rejected the key. Check it in Settings.")


class ProviderRateLimitedError(ProviderError):
    status_code = 429
    code = "provider_rate_limited"

    def __init__(self, retry_after_seconds: float | None) -> None:
        super().__init__(
            "The AI provider is limiting requests for this key. Wait a minute and try again.",
            retry_after_seconds=retry_after_seconds,
        )


class ProviderUnavailableError(ProviderError):
    """No usable answer came back: the network failed, or the provider did."""

    code = "provider_unavailable"

    def __init__(self, *, provider_side: bool = False) -> None:
        #: True when the provider answered, with an error of its own.
        self.provider_side = provider_side
        super().__init__(
            "The AI provider had a problem on its side. Try again in a little while."
            if provider_side
            else "Couldn’t reach the AI provider. Check your connection and try again."
        )


#: Why a model did not answer. "failing": the provider reported an error of its own.
#: "gone": the provider says there is no such model. "silent": nothing came in time.
ModelTrouble = Literal["failing", "gone", "silent"]

_MODEL_TROUBLE: dict[str, str] = {
    "gone": ("The AI provider’s model isn’t available right now. Try again in a little while."),
    "silent": ("The AI provider took too long to answer. Try again in a little while."),
}


class ProviderModelUnavailableError(ProviderUnavailableError):
    """The provider was reached, but this model did not answer: failing, gone, or silent.

    For a provider with one model this is the provider being unavailable, and reads as
    such. For one with several, the gateway asks the next (ADR-021).
    """

    def __init__(self, trouble: ModelTrouble = "failing") -> None:
        super().__init__(provider_side=True)
        self.trouble: ModelTrouble = trouble
        if trouble in _MODEL_TROUBLE:
            self.message = _MODEL_TROUBLE[trouble]
            self.args = (self.message,)


class NoModelAnsweredError(ProviderUnavailableError):
    """Every model of a provider that has several was asked, and none answered."""

    def __init__(self, provider_name: str, model_names: Sequence[str]) -> None:
        super().__init__(provider_side=True)
        self.message = (
            f"None of {provider_name}’s models answered ({', '.join(model_names)}). Try again in "
            "a little while."
        )
        self.args = (self.message,)


class ProviderRequestRefusedError(ProviderError):
    code = "provider_request_refused"

    def __init__(self) -> None:
        super().__init__("The AI provider refused the request. You can try again.")


class ProviderBadResponseError(ProviderError):
    code = "provider_bad_response"

    def __init__(self) -> None:
        super().__init__("Couldn’t read the AI provider’s answer. You can try again.")


#: How the documented provider marks an answer it wrote itself, in the model's place.
_NOTICE_ID_PREFIX = "chatcmpl-fake"
#: How much of a provider's notice is shown. Enough for a sentence or two and an address.
MAX_NOTICE_CHARACTERS = 300
# Control characters, and the characters that reorder or hide text.
_UNPRINTABLE = re.compile("[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")


def clean_notice(text: str) -> str:
    """A provider's own words made safe to show: one line, nothing hidden, not too long.

    They are somebody else's text. They are shown, quoted, because they are the only
    thing that says what the learner can do; they are never interpreted or followed.
    """
    one_line = " ".join(_UNPRINTABLE.sub(" ", text).split())
    if len(one_line) > MAX_NOTICE_CHARACTERS:
        one_line = one_line[: MAX_NOTICE_CHARACTERS - 1].rstrip() + "\u2026"
    return one_line.replace('"', "'")


class ProviderNoticeError(ProviderError):
    """The provider answered in the model's place, with a notice of its own.

    Seen with the documented provider on 2026-11-20: a request to an account that had not
    been topped up came back as an ordinary, successful completion whose text was a
    sentence about the account's allowance, with an identifier beginning
    ``chatcmpl-fake`` and no tokens used. Taken for the model's answer, that sentence is
    an unreadable draft, the job asks again, and the learner is told only that the
    lesson could not be used, having spent two requests to learn nothing.
    """

    code = "provider_notice"

    def __init__(self, notice: str) -> None:
        self.notice = clean_notice(notice)
        said = f' It said: "{self.notice}"' if self.notice else ""
        super().__init__(
            f"The AI provider returned an account notice instead of an answer.{said} This is "
            "about your account with the provider, not Adle."
        )


def _looks_like_a_notice(response_id: object, text: str, usage: dict[str, Any] | None) -> bool:
    """Whether a successful answer was written by the provider and not by the model."""
    if isinstance(response_id, str) and response_id.startswith(_NOTICE_ID_PREFIX):
        return True
    # A model cannot write anything without reading and writing tokens. An answer that
    # has text and reports that none were used did not come from one.
    return (
        bool(text.strip())
        and usage is not None
        and _count(usage, "prompt_tokens") == 0
        and _count(usage, "completion_tokens") == 0
    )


class RequestCancelledError(Exception):
    """The caller asked to stop while the request was in flight."""


#: Where a streamed chunk carries what the model thought before it answered.
_THINKING_FIELDS = ("reasoning_content", "reasoning")

#: What a model is seen to be doing while its answer is on the way.
Stage = Literal["thinking", "writing"]

#: How often whoever is waiting for an answer looks up to see whether it is still wanted.
_LOOK_UP_SECONDS = 0.2


# -- one request -----------------------------------------------------------------


#: What one picture of a page counts for, in tokens, before a provider has said: 2,285 for a
#: page and its instruction, at 150 dots to the inch (2026-11-24, ADR-060).
PICTURE_TOKENS = 2_400


@dataclass(frozen=True, slots=True)
class ChatRequest:
    #: What the request is for: recorded with the usage, never sent.
    purpose: str
    system: str
    user: str
    max_output_tokens: int
    #: Ask for a single JSON object.
    json_output: bool = False
    #: Pictures sent with the user's words, each a PNG: a page to be read (ADR-060). Only
    #: a model that sees pictures (``ModelSpec.images``) is sent any.
    images: tuple[bytes, ...] = ()


@dataclass(frozen=True, slots=True)
class ChatResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    #: False when the provider did not say how many tokens were used.
    usage_reported: bool
    finish_reason: str | None
    #: How much the model thought before it answered, in characters, where the provider
    #: shows it. Never kept or read: counted, so that an estimate of tokens includes it.
    thinking_characters: int = 0
    #: Which model answered, as a person would name it. Set by the client.
    model_name: str = ""
    #: The model that was meant to answer and was not available, when another stood in
    #: for it. Set by the gateway; empty when the first choice answered.
    instead_of: str = ""
    #: Which provider answered, by its name. Set by the gateway.
    provider_name: str = ""
    #: The provider that was asked first and could not answer, when the learner let Adle
    #: use more than one and another stood in. Set by the gateway; otherwise empty.
    instead_of_provider: str = ""


def _never_cancelled() -> bool:
    return False


class ChatClient:
    """Sends one chat completion and reads the streamed answer."""

    def __init__(
        self,
        config: ProviderConfig,
        vault: CredentialVault,
        *,
        transport: httpx.BaseTransport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._vault = vault
        self._monotonic = monotonic
        self._client = httpx.Client(
            transport=transport,
            # Nothing from the environment decides where the key goes.
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(
                connect=config.connect_timeout_seconds,
                read=config.read_timeout_seconds,
                write=30.0,
                pool=15.0,
            ),
            headers={"User-Agent": "Adle", "Accept": "text/event-stream, application/json"},
        )

    def close(self) -> None:
        self._client.close()

    @property
    def vault(self) -> CredentialVault:
        return self._vault

    @property
    def has_key(self) -> bool:
        """Whether there is a key for this provider. Another provider's key does not count."""
        return self._vault.has_key_for(self.config.provider_id)

    def complete(
        self,
        request: ChatRequest,
        *,
        model: ModelSpec | None = None,
        cancelled: Callable[[], bool] = _never_cancelled,
        on_stage: Callable[[Stage], None] | None = None,
        on_piece: Callable[[str], None] | None = None,
    ) -> ChatResult:
        """Ask one model of this provider. ``model`` is the provider's first unless given.

        ``on_stage`` is told when the model is seen to begin thinking, and when it begins
        to write its answer: once each, at most. ``on_piece`` is handed each piece of the
        answer as it arrives, in order, and never any of the model's thinking: enough to
        say how far a long answer has come before it is whole.

        Raises ``RequestCancelledError`` as soon as ``cancelled`` turns true, however
        silent the provider is being. A model can take a minute before its first word,
        and "Stop" must not take a minute too. The request itself is made on a thread of
        its own, which lets go of the connection the next time anything arrives on it.
        """
        spec = model or self.config.models[0]
        if spec not in self.config.models:
            raise ValueError("That model does not belong to this provider.")
        if cancelled is _never_cancelled:
            # Nobody can change their mind, so there is nothing to wait beside.
            return self._send(request, spec, cancelled, on_stage, on_piece=on_piece)

        given_up = threading.Event()
        outcome: queue.Queue[ChatResult | BaseException] = queue.Queue(maxsize=1)
        answers: list[httpx.Response] = []

        def no_longer_wanted() -> bool:
            return given_up.is_set() or cancelled()

        def stage_while_wanted(stage: Stage) -> None:
            if on_stage is not None and not given_up.is_set():
                on_stage(stage)

        def piece_while_wanted(piece: str) -> None:
            if on_piece is not None and not given_up.is_set():
                on_piece(piece)

        def hang_up() -> None:
            # Closing the answer ends the request at the provider, instead of leaving it
            # to be written for nobody until its next line or the time limit. Best effort:
            # if it cannot be closed from here, the worker stops at the next thing it reads.
            for answer in list(answers):
                with contextlib.suppress(Exception):
                    answer.close()

        def opened(answer: httpx.Response) -> None:
            answers.append(answer)
            if given_up.is_set():
                hang_up()

        def work() -> None:
            try:
                outcome.put(
                    self._send(
                        request,
                        spec,
                        no_longer_wanted,
                        stage_while_wanted,
                        opened,
                        on_piece=piece_while_wanted,
                    )
                )
            except BaseException as error:  # handed to whoever asked, or dropped with them
                outcome.put(error)

        threading.Thread(target=work, name="adle-provider-request", daemon=True).start()
        while True:
            try:
                found = outcome.get(timeout=_LOOK_UP_SECONDS)
            except queue.Empty:
                if cancelled():
                    given_up.set()
                    hang_up()
                    raise RequestCancelledError from None
                continue
            if isinstance(found, BaseException):
                raise found
            return found

    def _send(
        self,
        request: ChatRequest,
        spec: ModelSpec,
        cancelled: Callable[[], bool],
        on_stage: Callable[[Stage], None] | None,
        opened: Callable[[httpx.Response], None] | None = None,
        *,
        on_piece: Callable[[str], None] | None = None,
    ) -> ChatResult:
        """Make the request and read the answer. Blocks for as long as the provider does.

        ``opened`` is handed the answer as soon as there is one, so that whoever is
        waiting beside this can close it.
        """
        # This provider's key, and no other's: a key goes only to the address it was given for.
        api_key = self._vault.api_key(self.config.provider_id)
        if api_key is None:
            raise ProviderKeyMissingError
        if request.images and not spec.images:
            # The gateway asks only models that see pictures for one; this is a mistake.
            raise ValueError("That model is not sent pictures.")
        user: str | list[dict[str, Any]] = request.user
        if request.images:
            user = [
                {"type": "text", "text": request.user},
                *(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(picture).decode("ascii")
                        },
                    }
                    for picture in request.images
                ),
            ]
        body: dict[str, Any] = {
            "model": spec.id,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": user},
            ],
            # No sampling parameters: every model is left at what its provider set. The
            # bound below also covers a model's thinking, hence the floor for those that think.
            "max_tokens": max(request.max_output_tokens, spec.min_max_tokens),
            "stream": True,
        }
        if spec.usage_option:
            body["stream_options"] = {"include_usage": True}
        effort = spec.effort(request.purpose)
        if effort is not None:
            body["reasoning_effort"] = effort
        if request.json_output and spec.json_mode:
            body["response_format"] = {"type": "json_object"}

        deadline = self._monotonic() + self.config.total_timeout_seconds
        try:
            with self._client.stream(
                "POST",
                f"{self.config.base_url}/chat/completions",
                json=body,
                # Not compressed: a few bytes must not be able to unfold into a great many.
                headers={"Authorization": f"Bearer {api_key}", "Accept-Encoding": "identity"},
            ) as response:
                if opened is not None:
                    opened(response)
                self._raise_for_status(response)
                return replace(
                    self._read(response, cancelled, deadline, on_stage, on_piece),
                    model_name=spec.name,
                )
        except (httpx.ConnectTimeout, httpx.PoolTimeout) as error:
            # The provider itself could not be reached; no model of it would do better.
            logger.warning("provider.timeout purpose=%s", request.purpose)
            raise ProviderUnavailableError from error
        except httpx.TimeoutException as error:
            # Reached, and silent: this model is not answering.
            logger.warning("provider.silent purpose=%s", request.purpose)
            raise ProviderModelUnavailableError("silent") from error
        except httpx.TransportError as error:
            # The exception text can contain the address; the class name is enough.
            logger.warning(
                "provider.unreachable purpose=%s error=%s", request.purpose, type(error).__name__
            )
            raise ProviderUnavailableError from error

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if status < 300:
            return
        logger.warning("provider.refused status=%s", status)
        if status in (401, 403):
            raise ProviderKeyRejectedError
        if status == 429:
            raise ProviderRateLimitedError(_retry_after(response.headers.get("retry-after")))
        if status >= 500:
            raise ProviderModelUnavailableError
        if status in (404, 410):
            # How a provider says "there is no such model", or "not any more".
            raise ProviderModelUnavailableError("gone")
        if 300 <= status < 400:
            # A redirect is not followed: the key goes only where it was configured to go.
            raise ProviderUnavailableError
        raise ProviderRequestRefusedError

    def _read(
        self,
        response: httpx.Response,
        cancelled: Callable[[], bool],
        deadline: float,
        on_stage: Callable[[Stage], None] | None = None,
        on_piece: Callable[[str], None] | None = None,
    ) -> ChatResult:
        def still_wanted() -> None:
            if cancelled():
                raise RequestCancelledError
            if self._monotonic() > deadline:
                raise httpx.ReadTimeout("the answer took too long")

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            # A server that ignores "stream" answers with one JSON document.
            return _result_from_document(_bounded_body(response, still_wanted))

        pieces: list[str] = []
        size = 0
        thinking = 0
        usage: dict[str, Any] | None = None
        finish_reason: str | None = None
        response_id: object = None
        saw_data = False
        stage: Stage | None = None

        def reached(now: Stage) -> None:
            # Forward only: a model that thinks again while it writes is still writing.
            nonlocal stage
            if stage != now and stage != "writing":
                stage = now
                if on_stage is not None:
                    on_stage(now)

        # Asked on every piece that arrives, whatever it carries: a model's thinking and
        # a provider's keep-alive lines are not answers, but each is a moment to stop.
        for payload in _events(response, still_wanted):
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except ValueError as error:
                raise ProviderBadResponseError from error
            if not isinstance(chunk, dict):
                raise ProviderBadResponseError
            if isinstance(chunk.get("error"), dict):
                logger.warning("provider.stream_error")
                raise ProviderModelUnavailableError
            saw_data = True
            if response_id is None:
                response_id = chunk.get("id")
            if isinstance(chunk.get("usage"), dict):
                usage = chunk["usage"]
            for choice in chunk.get("choices") or []:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                text = delta.get("content") if isinstance(delta, dict) else None
                if isinstance(delta, dict):
                    # A model's thinking arrives beside its answer. It is not the answer
                    # and is not kept; its length is, because it was paid for in tokens.
                    for name in _THINKING_FIELDS:
                        thought = delta.get(name)
                        if isinstance(thought, str) and thought:
                            thinking += len(thought)
                            reached("thinking")
                if isinstance(text, str) and text:
                    size += len(text)
                    if size > MAX_RESPONSE_CHARACTERS:
                        raise ProviderBadResponseError
                    pieces.append(text)
                    reached("writing")
                    if on_piece is not None:
                        on_piece(text)
                if isinstance(choice.get("finish_reason"), str):
                    finish_reason = choice["finish_reason"]
        if not saw_data:
            raise ProviderBadResponseError
        text = "".join(pieces)
        if _looks_like_a_notice(response_id, text, usage):
            # Its words are for the learner, not for the log.
            logger.warning("provider.notice")
            raise ProviderNoticeError(text)
        return replace(_result(text, usage, finish_reason), thinking_characters=thinking)


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None  # an HTTP date: not worth trusting a remote clock for
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_SECONDS)


def _lines(response: httpx.Response, on_piece: Callable[[], None]) -> Iterator[str]:
    """The lines of an answer as they arrive, with a bound on each and on all of them.

    The HTTP library's own line reader keeps a line in memory until its end arrives,
    however long that takes and however much comes first. A provider that never sends
    a newline could fill the memory that way, with "Stop" and the time limit never
    asked. Here ``on_piece`` is called for every piece received, complete line or not.
    """
    held = ""
    total = 0
    after_return = False
    for piece in response.iter_text():
        on_piece()
        total += len(piece)
        if total > MAX_STREAM_CHARACTERS:
            raise ProviderBadResponseError
        if after_return and piece.startswith("\n"):
            # The two halves of one line ending, in two pieces.
            piece = piece[1:]
        after_return = piece.endswith("\r")
        held += piece
        if "\n" not in piece and "\r" not in piece:
            if len(held) > MAX_LINE_CHARACTERS:
                raise ProviderBadResponseError
            continue
        *complete, held = held.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if len(held) > MAX_LINE_CHARACTERS:
            raise ProviderBadResponseError
        yield from complete
    if held:
        yield held


def _events(response: httpx.Response, on_piece: Callable[[], None]) -> Iterator[str]:
    """The ``data:`` payloads of a server-sent event stream, one per event.

    ``on_piece`` is called for everything received, including what carries nothing.
    """
    data: list[str] = []
    for line in _lines(response, on_piece):
        # Asked again for every line: many may arrive in one piece.
        on_piece()
        if line == "":
            if data:
                yield "\n".join(data)
                data = []
            continue
        if line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        yield "\n".join(data)


def _bounded_body(response: httpx.Response, on_piece: Callable[[], None]) -> str:
    chunks: list[str] = []
    size = 0
    for text in response.iter_text():
        # A document dripped slowly is stopped by "Stop" and by the time limit like a stream.
        on_piece()
        size += len(text)
        if size > MAX_RESPONSE_CHARACTERS * 2:
            raise ProviderBadResponseError
        chunks.append(text)
    return "".join(chunks)


def _result_from_document(body: str) -> ChatResult:
    try:
        document = json.loads(body)
        choice = document["choices"][0]
        text = choice["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise ProviderBadResponseError from error
    if not isinstance(text, str):
        raise ProviderBadResponseError
    usage = document.get("usage") if isinstance(document, dict) else None
    reason = choice.get("finish_reason") if isinstance(choice, dict) else None
    usage = usage if isinstance(usage, dict) else None
    response_id = document.get("id") if isinstance(document, dict) else None
    if _looks_like_a_notice(response_id, text, usage):
        logger.warning("provider.notice")
        raise ProviderNoticeError(text)
    return _result(text, usage, reason if isinstance(reason, str) else None)


def _count(usage: dict[str, Any] | None, name: str) -> int | None:
    value = usage.get(name) if usage else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _result(text: str, usage: dict[str, Any] | None, finish_reason: str | None) -> ChatResult:
    prompt_tokens = _count(usage, "prompt_tokens")
    completion_tokens = _count(usage, "completion_tokens")
    reported = prompt_tokens is not None and completion_tokens is not None
    return ChatResult(
        text=text,
        prompt_tokens=prompt_tokens or 0,
        completion_tokens=completion_tokens or 0,
        usage_reported=reported,
        finish_reason=finish_reason,
    )
