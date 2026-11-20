"""An answer the provider wrote itself, in the model's place.

On 2026-11-20 the documented provider answered a request from an account that had not
been topped up with HTTP 200 and an ordinary completion whose text was a sentence about
the account's allowance. The two shapes below are what arrived, word for word, streamed
and not. Nothing in this file leaves the process.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from adle_core.application.services import Services
from adle_core.generation.credentials import CredentialVault
from adle_core.generation.provider import (
    MAX_NOTICE_CHARACTERS,
    ChatClient,
    ChatRequest,
    ProviderConfig,
    ProviderNoticeError,
    clean_notice,
)
from adle_core.infrastructure.orm import ModelUsage
from tests.support.model import LESSON, FakeProvider
from tests.unit.test_generation_api import (
    KEY,
    add_concept,
    finished,
    lesson_count,
    topic_course,
)

NOTICE = (
    "Sorry, to prevent abuse of free resources, accounts that have not been recharged can "
    "only try 10 times. You can increase the free quota after recharging; "
    "https://console.aihubmix.com/topup"
)
REQUEST = ChatRequest(
    purpose="lesson",
    system="You write lessons.",
    user="Write about weights.",
    max_output_tokens=2000,
    json_output=True,
)


def streamed(text: str = NOTICE, *, response_id: str = "chatcmpl-fake-1795158495575810024") -> Any:
    """The notice as it arrived when the request asked for a stream: one chunk, no usage."""
    chunk = {
        "choices": [
            {
                "delta": {"content": text, "role": "assistant"},
                "finish_reason": "stop",
                "index": 0,
            }
        ],
        "created": 1795158495,
        "id": response_id,
        "model": "coding-kimi-k3-free",
        "object": "chat.completion.chunk",
    }
    body = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)


def document(
    text: str = NOTICE,
    *,
    response_id: str = "chatcmpl-fake-1795158467073593830",
    usage: dict[str, int] | None = None,
) -> httpx.Response:
    """The notice as it arrived when the request did not ask for a stream."""
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {"content": text, "role": "assistant"},
                }
            ],
            "created": 1795158467,
            "id": response_id,
            "model": "coding-kimi-k3-free",
            "object": "chat.completion",
            "usage": usage
            if usage is not None
            else {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
        },
    )


def ask(response: httpx.Response) -> Any:
    vault = CredentialVault()
    vault.set_api_key(KEY)
    client = ChatClient(ProviderConfig(), vault, transport=httpx.MockTransport(lambda _: response))
    try:
        return client.complete(REQUEST)
    finally:
        client.close()


@pytest.fixture
def keyed(client: TestClient) -> TestClient:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    return client


# -- the client ------------------------------------------------------------------


@pytest.mark.parametrize("response", [streamed(), document()], ids=["streamed", "not streamed"])
def test_a_notice_from_the_provider_is_not_taken_for_the_models_answer(
    response: httpx.Response,
) -> None:
    with pytest.raises(ProviderNoticeError) as raised:
        ask(response)

    error = raised.value
    assert error.code == "provider_notice"
    assert error.notice == NOTICE
    # The learner is told whose words these are, what they are about, and that nothing changed.
    assert error.message == (
        "The AI provider answered with a notice of its own instead of passing this to the "
        f'model. It said: "{NOTICE}" This is about your account with the provider, not about '
        "Adle. Nothing was changed."
    )


def test_an_answer_that_used_no_tokens_is_a_notice_whatever_it_is_called() -> None:
    """A model cannot write without reading and writing tokens."""
    with pytest.raises(ProviderNoticeError):
        ask(document(response_id="chatcmpl-9f2c41"))


def test_an_ordinary_answer_is_still_an_ordinary_answer() -> None:
    lesson = json.dumps(LESSON)
    counted = {"prompt_tokens": 900, "completion_tokens": 400, "total_tokens": 1300}
    result = ask(document(lesson, response_id="chatcmpl-9f2c41", usage=counted))
    assert result.text == lesson
    assert (result.prompt_tokens, result.completion_tokens) == (900, 400)

    # Nor is a stream that simply does not report its usage: silence is not zero.
    unreported = ask(streamed(lesson, response_id="chatcmpl-9f2c41"))
    assert unreported.text == lesson
    assert not unreported.usage_reported


def test_the_words_of_a_notice_reach_the_learner_and_not_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG), pytest.raises(ProviderNoticeError):
        ask(streamed())
    assert "provider.notice" in caplog.text
    assert "recharged" not in caplog.text
    assert "topup" not in caplog.text
    assert KEY not in caplog.text


def test_a_notice_is_shown_as_one_plain_line_of_limited_length() -> None:
    hostile = 'First line.\r\nSecond line.\x00\x07 ‮gnp.exe‬ He said "pay here" ​' + "x" * 5000

    cleaned = clean_notice(hostile)

    assert len(cleaned) == MAX_NOTICE_CHARACTERS
    assert cleaned.endswith("…")
    assert cleaned.startswith("First line. Second line. gnp.exe He said 'pay here' xxx")
    # Nothing that breaks a line, hides text, turns it round, or closes the quotation.
    assert not any(ord(character) < 32 for character in cleaned)
    assert not {"‮", "‬", "​", '"'} & set(cleaned)

    with pytest.raises(ProviderNoticeError) as raised:
        ask(streamed(hostile))
    assert raised.value.message.count('"') == 2


def test_a_notice_with_no_words_still_says_what_happened() -> None:
    with pytest.raises(ProviderNoticeError) as raised:
        ask(document("   \n "))
    assert raised.value.notice == ""
    assert "It said" not in raised.value.message
    assert "instead of passing this to the model." in raised.value.message


# -- a job ---------------------------------------------------------------------------


def test_a_notice_ends_a_lesson_job_at_once_with_the_providers_words(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course = topic_course(keyed)
    concept = add_concept(keyed, course["id"])
    provider.queue(streamed())

    job = finished(services, keyed.post(f"/v1/concepts/{concept}/lessons"))

    assert (job["status"], job["error_code"]) == ("failed", "provider_notice")
    assert "accounts that have not been recharged can only try 10 times" in job["error_message"]
    assert "about your account with the provider" in job["error_message"]
    assert KEY not in job["error_message"]
    # It is not a draft to be asked for again: an account with ten tries has nine left.
    assert len(provider.requests) == 1
    assert lesson_count(services) == 0
    # The request did go out, and is counted as one.
    with services.database.read() as session:
        assert session.scalar(select(func.count(ModelUsage.id))) == 1


def test_a_notice_ends_a_curriculum_job_at_once_too(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    course = topic_course(keyed)
    provider.queue(document())

    job = finished(services, keyed.post(f"/v1/courses/{course['id']}/curriculum/proposal"))

    assert (job["status"], job["error_code"]) == ("failed", "provider_notice")
    assert len(provider.requests) == 1
    assert keyed.get(f"/v1/courses/{course['id']}/curriculum").json()["concepts"] == []
