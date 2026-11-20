"""The model provider: one OpenAI-compatible chat completion at a time.

This is the only module that sends anything off the computer. It knows how to
make one request and read one answer; deciding *whether* a request may be sent
(quota), *what* to ask (prompts), and what to do with the answer (validation)
all happen elsewhere.

Rules that hold here:

* The key is read from the vault for each request and placed in one header.
  It is never logged, stored, or put in an error message.
* Requests go only to the configured base URL. Redirects are not followed, and
  proxy or credential settings from the environment are not used.
* Nothing from a request or a response body is logged. Errors carry a status
  code and a fixed sentence.
* A response is bounded in size and in time, and can be abandoned between
  chunks when the learner cancels.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx2 as httpx

from adle_core.errors import AdleError
from adle_core.generation.credentials import CredentialVault

logger = logging.getLogger(__name__)

BASE_URL_ENV = "ADLE_PROVIDER_BASE_URL"
MODEL_ENV = "ADLE_PROVIDER_MODEL"

DEFAULT_BASE_URL = "https://aihubmix.com/v1"
DEFAULT_MODEL = "coding-kimi-k3-free"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

#: An answer longer than this is not a lesson; it is a model that did not stop.
MAX_RESPONSE_CHARACTERS = 400_000
#: Upper bound honoured for a ``Retry-After`` header.
MAX_RETRY_AFTER_SECONDS = 90.0


class ProviderConfigError(ValueError):
    """The provider settings are not something Adle will send data to."""


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider_id: str = "aihubmix"
    display_name: str = "AIHubMix"
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    connect_timeout_seconds: float = 15.0
    #: The longest silence tolerated while an answer is arriving.
    read_timeout_seconds: float = 120.0
    #: The longest one request may take in all.
    total_timeout_seconds: float = 420.0

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
        if base_url.rstrip("/") == DEFAULT_BASE_URL:
            return cls(base_url=DEFAULT_BASE_URL, model=model)
        return cls(
            provider_id="custom",
            display_name=f"Custom endpoint ({host})",
            base_url=base_url.rstrip("/"),
            model=model,
        )


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


class ProviderKeyRejectedError(ProviderError):
    status_code = 409
    code = "provider_key_rejected"

    def __init__(self) -> None:
        super().__init__(
            "The AI provider did not accept the key. Check it in Settings, under AI provider."
        )


class ProviderRateLimitedError(ProviderError):
    status_code = 429
    code = "provider_rate_limited"

    def __init__(self, retry_after_seconds: float | None) -> None:
        super().__init__(
            "The AI provider is limiting requests for this key at the moment. "
            "Wait a minute and try again.",
            retry_after_seconds=retry_after_seconds,
        )


class ProviderUnavailableError(ProviderError):
    """No usable answer came back: the network failed, or the provider did."""

    code = "provider_unavailable"

    def __init__(self, *, provider_side: bool = False) -> None:
        #: True when the provider answered, with an error of its own.
        self.provider_side = provider_side
        super().__init__(
            "The AI provider reported a problem on its side. Nothing was changed; "
            "try again in a little while."
            if provider_side
            else "The AI provider could not be reached. Check your connection and try again."
        )


class ProviderRequestRefusedError(ProviderError):
    code = "provider_request_refused"

    def __init__(self) -> None:
        super().__init__(
            "The AI provider refused the request. Nothing was changed; you can try again."
        )


class ProviderBadResponseError(ProviderError):
    code = "provider_bad_response"

    def __init__(self) -> None:
        super().__init__(
            "The AI provider's answer could not be read. Nothing was changed; you can try again."
        )


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
            "The AI provider answered with a notice of its own instead of passing this to "
            f"the model.{said} This is about your account with the provider, not about "
            "Adle. Nothing was changed."
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


# -- one request -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChatRequest:
    #: What the request is for: recorded with the usage, never sent.
    purpose: str
    system: str
    user: str
    max_output_tokens: int
    #: Ask for a single JSON object.
    json_output: bool = False


@dataclass(frozen=True, slots=True)
class ChatResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    #: False when the provider did not say how many tokens were used.
    usage_reported: bool
    finish_reason: str | None


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
    def has_key(self) -> bool:
        return self._vault.has_api_key

    def complete(
        self, request: ChatRequest, *, cancelled: Callable[[], bool] = _never_cancelled
    ) -> ChatResult:
        api_key = self._vault.api_key()
        if api_key is None:
            raise ProviderKeyMissingError
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            # No sampling parameters: the documented model fixes them, and its provider
            # advises leaving them out. The bound below also covers the model's thinking.
            "max_tokens": request.max_output_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if request.json_output:
            body["response_format"] = {"type": "json_object"}

        deadline = self._monotonic() + self.config.total_timeout_seconds
        try:
            with self._client.stream(
                "POST",
                f"{self.config.base_url}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {api_key}"},
            ) as response:
                self._raise_for_status(response)
                return self._read(response, cancelled, deadline)
        except httpx.TimeoutException as error:
            logger.warning("provider.timeout purpose=%s", request.purpose)
            raise ProviderUnavailableError from error
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
            raise ProviderUnavailableError(provider_side=True)
        if 300 <= status < 400:
            # A redirect is not followed: the key goes only where it was configured to go.
            raise ProviderUnavailableError
        raise ProviderRequestRefusedError

    def _read(
        self, response: httpx.Response, cancelled: Callable[[], bool], deadline: float
    ) -> ChatResult:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            # A server that ignores "stream" answers with one JSON document.
            return _result_from_document(_bounded_body(response))

        pieces: list[str] = []
        size = 0
        usage: dict[str, Any] | None = None
        finish_reason: str | None = None
        response_id: object = None
        saw_data = False
        for payload in _events(response):
            if cancelled():
                raise RequestCancelledError
            if self._monotonic() > deadline:
                raise httpx.ReadTimeout("the answer took too long")
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
                raise ProviderUnavailableError(provider_side=True)
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
                if isinstance(text, str) and text:
                    size += len(text)
                    if size > MAX_RESPONSE_CHARACTERS:
                        raise ProviderBadResponseError
                    pieces.append(text)
                if isinstance(choice.get("finish_reason"), str):
                    finish_reason = choice["finish_reason"]
        if not saw_data:
            raise ProviderBadResponseError
        text = "".join(pieces)
        if _looks_like_a_notice(response_id, text, usage):
            # Its words are for the learner, not for the log.
            logger.warning("provider.notice")
            raise ProviderNoticeError(text)
        return _result(text, usage, finish_reason)


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None  # an HTTP date: not worth trusting a remote clock for
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_SECONDS)


def _events(response: httpx.Response) -> Iterator[str]:
    """The ``data:`` payloads of a server-sent event stream, one per event."""
    data: list[str] = []
    for line in response.iter_lines():
        if line == "":
            if data:
                yield "\n".join(data)
                data = []
            continue
        if line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        yield "\n".join(data)


def _bounded_body(response: httpx.Response) -> str:
    chunks: list[str] = []
    size = 0
    for text in response.iter_text():
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
