"""Parsing in a real child process: results cross the boundary, and runaway parses are stopped."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import httpx2 as httpx
import pytest

from adle_core.ingestion.extract import extract_isolated, worker_command
from adle_core.ingestion.types import DEFAULT_LIMITS, DocumentKind, IngestionError

DOCUMENTS = Path(__file__).resolve().parents[4] / "fixtures" / "sample-documents"
TOKEN = "integration-launch-token-0123456789abcdef"


@pytest.mark.slow
def test_a_document_is_parsed_in_a_child_process_and_returned_intact() -> None:
    document = extract_isolated(DOCUMENTS / "lecture-notes.pdf", "lecture-notes.pdf")
    assert document.kind is DocumentKind.PDF
    assert [section.page_number for section in document.sections] == [1, 2, 3]
    assert "mean squared error" in document.sections[0].text


@pytest.mark.slow
def test_parser_errors_cross_the_process_boundary_with_their_code() -> None:
    with pytest.raises(IngestionError) as raised:
        extract_isolated(DOCUMENTS / "lecture-notes-encrypted.pdf", "locked.pdf")
    assert raised.value.code == "encrypted_document"
    assert "password-protected" in raised.value.message


@pytest.mark.slow
def test_a_parse_that_runs_past_its_time_limit_is_killed() -> None:
    # No real parse can finish before a child process has even started.
    impatient = replace(DEFAULT_LIMITS, parse_timeout_seconds=0.001)
    started = time.monotonic()
    with pytest.raises(IngestionError) as raised:
        extract_isolated(DOCUMENTS / "lecture-notes.pdf", "lecture-notes.pdf", impatient)
    assert raised.value.code == "parse_timeout"
    assert "took too long" in raised.value.message
    # The caller gets control back promptly instead of waiting for the child.
    assert time.monotonic() - started < 10


def test_type_detection_happens_before_any_process_is_started() -> None:
    with pytest.raises(IngestionError) as raised:
        extract_isolated(DOCUMENTS / "not-really-a.pdf", "not-really-a.pdf")
    assert raised.value.code == "unsupported_type"


def test_the_worker_command_runs_the_worker_module() -> None:
    assert worker_command() == [sys.executable, "-m", "adle_core.ingestion.worker"]


@pytest.mark.slow
def test_the_worker_answers_garbage_input_with_a_clean_error() -> None:
    completed = subprocess.run(  # noqa: S603 - fixed argv
        worker_command(), input=b"this is not json", capture_output=True, timeout=30, check=True
    )
    assert json.loads(completed.stdout) == {
        "ok": False,
        "code": "malformed_document",
        "message": "The file could not be read. It may be damaged.",
    }


@pytest.mark.slow
def test_import_completes_inside_the_real_service_process(tmp_path: Path) -> None:
    """Regression: imports hung forever when the service ran as the desktop app starts it.

    The service keeps a thread blocked on its stdin to notice the app closing.
    On Windows a parser child that shared that stdin handle hung at start-up, so
    every import stalled at "1 of N". The in-process tests could not see this;
    this one runs the service exactly as Electron does and imports a real file.
    """
    process = subprocess.Popen(  # noqa: S603 - fixed argv
        [sys.executable, "-m", "adle_core", "--data-dir", str(tmp_path / "data")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(json.dumps({"token": TOKEN}) + "\n")
        process.stdin.flush()
        port = json.loads(process.stdout.readline())["port"]
        client = httpx.Client(
            base_url=f"http://127.0.0.1:{port}/v1",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10,
        )
        with client:
            course = client.post("/courses", json={"title": "T", "origin": "materials"}).json()
            job = client.post(
                f"/courses/{course['id']}/sources/import",
                json={
                    "paths": [
                        str(DOCUMENTS / "study-notes.txt"),
                        str(DOCUMENTS / "lecture-notes.pdf"),
                    ]
                },
            ).json()

            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                job = client.get(f"/jobs/{job['id']}").json()
                if job["status"] not in ("queued", "running"):
                    break
                time.sleep(0.1)

            assert job["status"] == "succeeded", job
            assert [entry["outcome"] for entry in job["result"]["files"]] == ["imported"] * 2
            hits = client.get(
                f"/courses/{course['id']}/search", params={"q": "learning rate"}
            ).json()["hits"]
            assert {hit["source_name"] for hit in hits} == {"study-notes.txt", "lecture-notes.pdf"}
    finally:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=15)
        for pipe in (process.stdout, process.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()
    assert process.returncode == 0
