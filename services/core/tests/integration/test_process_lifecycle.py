"""The real launch contract: start the service as a child process and talk to it."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest

from adle_core import __version__

TOKEN = "integration-launch-token-0123456789abcdef"
AUTHORISED = {"Authorization": f"Bearer {TOKEN}"}


@contextmanager
def core_process(
    cwd: Path, *arguments: str, env: dict[str, str] | None = None
) -> Iterator[subprocess.Popen[str]]:
    """Run `python -m adle_core`, always reaping the process and closing its pipes."""
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-m", "adle_core", *arguments],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env=env,
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=15)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()


@pytest.mark.slow
def test_handshake_serves_on_loopback_and_stops_when_stdin_closes(tmp_path: Path) -> None:
    with core_process(tmp_path, "--data-dir", str(tmp_path / "data")) as process:
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        process.stdin.write(json.dumps({"token": TOKEN}) + "\n")
        process.stdin.flush()

        event = json.loads(process.stdout.readline())
        assert event["event"] == "ready"
        assert event["version"] == __version__
        port = event["port"]
        assert isinstance(port, int)
        assert 0 < port < 65536

        base = f"http://127.0.0.1:{port}"
        authed = httpx.get(f"{base}/v1/health", headers={"Authorization": f"Bearer {TOKEN}"})
        assert authed.status_code == 200
        assert httpx.get(f"{base}/v1/health").status_code == 401

        # The token travels over stdin only: never in the process arguments.
        assert all(TOKEN not in str(argument) for argument in process.args)  # type: ignore[union-attr]

        # Closing stdin is the shutdown signal.
        process.stdin.close()
        assert process.wait(timeout=15) == 0
        with pytest.raises(httpx.TransportError):
            httpx.get(f"{base}/v1/health", timeout=2)

        assert TOKEN not in process.stderr.read(), "the launch token leaked into the service log"


@pytest.mark.slow
@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not json",
        json.dumps({"token": "short"}),
        json.dumps({"token": 12345}),
        json.dumps([]),
        # A restore is asked for with an absolute path, or not at all.
        json.dumps({"token": TOKEN, "restore_from": "relative/copy.adle"}),
        json.dumps({"token": TOKEN, "restore_from": ""}),
        json.dumps({"token": TOKEN, "restore_from": 7}),
        json.dumps({"token": TOKEN, "restore_from": ["C:/copies/copy.adle"]}),
    ],
)
def test_bad_handshake_fails_fast_with_a_fatal_event(tmp_path: Path, payload: str) -> None:
    with core_process(tmp_path, "--data-dir", str(tmp_path / "data")) as process:
        stdout, _ = process.communicate(payload + "\n" if payload else "", timeout=15)
        assert json.loads(stdout.splitlines()[0])["event"] == "fatal"
        assert process.returncode == 2


def shake_hands(process: subprocess.Popen[str], payload: dict[str, object]) -> dict[str, Any]:
    """Send the handshake line and return the first protocol line the service answers with."""
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    event: dict[str, Any] = json.loads(process.stdout.readline())
    return event


def stop(process: subprocess.Popen[str]) -> str:
    """Ask the service to stop the way the app does, and return what it logged."""
    assert process.stdin is not None
    assert process.stderr is not None
    process.stdin.close()
    assert process.wait(timeout=15) == 0
    return process.stderr.read()


def course_titles(base: str) -> list[str]:
    courses = httpx.get(f"{base}/v1/courses", headers=AUTHORISED).json()["courses"]
    return sorted(course["title"] for course in courses)


def add_course(base: str, title: str) -> None:
    body = {"title": title, "origin": "topic", "topic": "Something to learn"}
    assert httpx.post(f"{base}/v1/courses", headers=AUTHORISED, json=body).status_code == 201


@pytest.mark.slow
def test_a_restore_asked_for_in_the_handshake_happens_before_the_data_is_opened(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    copy = tmp_path / "kept elsewhere" / "Adle data.adle"
    copy.parent.mkdir()

    with core_process(tmp_path, "--data-dir", str(data)) as process:
        event = shake_hands(process, {"token": TOKEN})
        # No restore was asked for, so nothing is said about one.
        assert "restore" not in event
        base = f"http://127.0.0.1:{event['port']}"
        add_course(base, "In the copy")
        saved = httpx.post(f"{base}/v1/data/copy", headers=AUTHORISED, json={"path": str(copy)})
        assert saved.status_code == 204, saved.text
        add_course(base, "Added afterwards")
        stop(process)

    with core_process(tmp_path, "--data-dir", str(data)) as process:
        event = shake_hands(process, {"token": TOKEN, "restore_from": str(copy)})
        assert event["event"] == "ready"
        assert event["restore"] == {"ok": True}
        base = f"http://127.0.0.1:{event['port']}"
        assert course_titles(base) == ["In the copy"]
        log = stop(process)

    # The path is the learner's own and names their folders: it is not logged.
    assert "kept elsewhere" not in log
    assert "restored from a copy" in log
    # What was replaced is kept, and the learner's file is still one file.
    assert len(list((data / "backups").glob("adle-replaced-*.db"))) == 1
    assert [entry.name for entry in copy.parent.iterdir()] == [copy.name]

    # The next ordinary start is on the restored data, with nothing more to say.
    with core_process(tmp_path, "--data-dir", str(data)) as process:
        event = shake_hands(process, {"token": TOKEN})
        assert "restore" not in event
        assert course_titles(f"http://127.0.0.1:{event['port']}") == ["In the copy"]
        stop(process)


@pytest.mark.slow
def test_a_refused_restore_is_reported_and_the_service_runs_on_the_data_as_it_was(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    not_a_copy = tmp_path / "lecture notes.adle"
    not_a_copy.write_text("These are my lecture notes, not a copy of Adle's data.", "utf-8")

    with core_process(tmp_path, "--data-dir", str(data)) as process:
        event = shake_hands(process, {"token": TOKEN})
        add_course(f"http://127.0.0.1:{event['port']}", "Still here")
        stop(process)

    for offered in (not_a_copy, tmp_path / "does not exist.adle"):
        with core_process(tmp_path, "--data-dir", str(data)) as process:
            event = shake_hands(process, {"token": TOKEN, "restore_from": str(offered)})
            # Not fatal: the app is usable, and is told why nothing was restored.
            assert event["event"] == "ready"
            assert event["restore"]["ok"] is False
            assert "not changed" in event["restore"]["message"]
            assert str(offered) not in event["restore"]["message"]
            assert course_titles(f"http://127.0.0.1:{event['port']}") == ["Still here"]
            log = stop(process)
        assert "lecture notes" not in log

    assert not list((data / "backups").iterdir())


@pytest.mark.slow
def test_missing_data_directory_is_reported(tmp_path: Path) -> None:
    env = {key: value for key, value in os.environ.items() if key != "ADLE_DATA_DIR"}
    with core_process(tmp_path, env=env) as process:
        stdout, _ = process.communicate(json.dumps({"token": TOKEN}) + "\n", timeout=15)
        event = json.loads(stdout.splitlines()[0])
        assert event["event"] == "fatal"
        assert "data directory" in event["message"]
        assert process.returncode == 2
