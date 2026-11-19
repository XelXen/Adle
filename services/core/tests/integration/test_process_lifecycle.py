"""The real launch contract: start the service as a child process and talk to it."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx2 as httpx
import pytest

from adle_core import __version__

TOKEN = "integration-launch-token-0123456789abcdef"


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
    ["", "not json", json.dumps({"token": "short"}), json.dumps({"token": 12345}), json.dumps([])],
)
def test_bad_handshake_fails_fast_with_a_fatal_event(tmp_path: Path, payload: str) -> None:
    with core_process(tmp_path, "--data-dir", str(tmp_path / "data")) as process:
        stdout, _ = process.communicate(payload + "\n" if payload else "", timeout=15)
        assert json.loads(stdout.splitlines()[0])["event"] == "fatal"
        assert process.returncode == 2


@pytest.mark.slow
def test_missing_data_directory_is_reported(tmp_path: Path) -> None:
    env = {key: value for key, value in os.environ.items() if key != "ADLE_DATA_DIR"}
    with core_process(tmp_path, env=env) as process:
        stdout, _ = process.communicate(json.dumps({"token": TOKEN}) + "\n", timeout=15)
        event = json.loads(stdout.splitlines()[0])
        assert event["event"] == "fatal"
        assert "data directory" in event["message"]
        assert process.returncode == 2
