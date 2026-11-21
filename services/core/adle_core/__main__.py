"""Process entry point for the core service.

Launch contract with the Electron main process (see docs/architecture/overview.md):

1. The parent starts this process and writes one JSON line to stdin:
   ``{"token": "<random per-launch secret>"}``. The token never appears in
   argv or the environment.
2. This process binds 127.0.0.1 on an OS-assigned port and, once it is
   accepting connections, writes one JSON line to stdout:
   ``{"event": "ready", "port": <int>, "version": "<semver>"}``.
3. stdout carries nothing else. Diagnostics go to stderr.
4. When stdin reaches EOF (the parent exited or asked us to stop) the service
   shuts down gracefully. This prevents an orphaned backend.

The handshake line may also carry ``"restore_from": "<absolute path>"``: replace
the data with that copy before opening it (ADR-016). The data cannot be swapped
under a running service, so this is the only moment it can happen. The ``ready``
line then has ``"restore": {"ok": true}`` or ``{"ok": false, "message": "..."}``.
A refused restore is not fatal: the data is as it was and the service runs on it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import socket
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn

from adle_core import __version__
from adle_core.api.app import create_app
from adle_core.api.auth import LaunchToken
from adle_core.application.data_copy import restore_copy
from adle_core.application.services import build_services
from adle_core.config import Settings, SettingsError
from adle_core.generation.credentials import SecretRedactionFilter
from adle_core.infrastructure.migrate import MigrationError

logger = logging.getLogger("adle_core")

LOOPBACK = "127.0.0.1"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="adle-core", description="Adle local core service")
    parser.add_argument("--data-dir", help="App-controlled data directory (or ADLE_DATA_DIR).")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Loopback port to bind. 0 (default) lets the OS choose.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args(argv)


@dataclass(frozen=True, slots=True)
class Handshake:
    token: LaunchToken
    #: A copy of the data to put in place before anything is opened, if the learner asked.
    restore_from: Path | None = None


def _read_handshake() -> Handshake:
    """Read the launch token, and any one-time instruction, from the first line of stdin."""
    line = sys.stdin.readline()
    if not line:
        raise SettingsError("No launch handshake received on stdin.")
    malformed = SettingsError("The launch handshake was malformed.")
    try:
        payload: Any = json.loads(line)
    except json.JSONDecodeError as exc:
        raise malformed from exc
    if not isinstance(payload, dict):
        raise malformed
    token = payload.get("token")
    restore_from = payload.get("restore_from")
    if not isinstance(token, str):
        raise malformed
    copy: Path | None = None
    if restore_from is not None:
        if not isinstance(restore_from, str) or not restore_from or "\x00" in restore_from:
            raise malformed
        copy = Path(restore_from)
        if not copy.is_absolute():
            raise malformed
    try:
        return Handshake(LaunchToken(token), copy)
    except ValueError as exc:
        raise SettingsError(str(exc)) from exc


def _restore(settings: Settings, copy: Path) -> dict[str, Any]:
    """Replace the data with a saved copy. Returns what to tell the parent about it.

    The path is not logged: it is the learner's own, and names their folders.
    """
    try:
        restore_copy(settings, copy)
    except MigrationError as exc:
        logger.warning("The data was not restored from a copy (%s)", type(exc).__name__)
        return {"ok": False, "message": str(exc)}
    except Exception as exc:
        # Whatever it was, the service must still start.
        # Only the kind of failure is logged: its text may name the learner's file.
        logger.error("Restoring from a copy failed unexpectedly (%s)", type(exc).__name__)
        # True whatever happened: putting the copy in place is the last step, and atomic.
        return {
            "ok": False,
            "message": "Adle could not restore from that copy. Your current data was not changed.",
        }
    logger.info("The data was restored from a copy")
    return {"ok": True}


def _emit(event: dict[str, Any]) -> None:
    """Write one protocol line to stdout. The parent parses these."""
    sys.stdout.write(json.dumps(event, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _watch_parent(server: uvicorn.Server) -> None:
    """Stop the server when stdin closes, i.e. when the parent goes away."""

    def wait_for_eof() -> None:
        try:
            while sys.stdin.readline():
                pass
        except (OSError, ValueError):
            pass
        server.should_exit = True

    threading.Thread(target=wait_for_eof, name="adle-parent-watch", daemon=True).start()


async def _serve(
    server: uvicorn.Server, sock: socket.socket, restore: dict[str, Any] | None
) -> None:
    async def announce_when_started() -> None:
        while not server.started:
            if server.should_exit:
                return
            await asyncio.sleep(0.01)
        ready: dict[str, Any] = {
            "event": "ready",
            "port": sock.getsockname()[1],
            "version": __version__,
        }
        if restore is not None:
            ready["restore"] = restore
        _emit(ready)

    announcer = asyncio.create_task(announce_when_started())
    try:
        await server.serve(sockets=[sock])
    finally:
        announcer.cancel()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # The HTTP client writes a line for every request, with the address and whatever
    # reason phrase the other side chose to send. Neither belongs in the log.
    for chatty in ("httpx2", "httpcore2", "httpx", "httpcore"):
        logging.getLogger(chatty).setLevel(logging.WARNING)
    args = _parse_args(argv)
    try:
        settings = Settings.from_environment(args.data_dir)
        settings.ensure_directories()
        handshake = _read_handshake()
    except SettingsError as exc:
        _emit({"event": "fatal", "message": str(exc)})
        return 2

    restore: dict[str, Any] | None = None
    if handshake.restore_from is not None:
        restore = _restore(settings, handshake.restore_from)

    try:
        services = build_services(settings, handshake.token)
    except MigrationError as exc:
        # The message is written for the learner and already says the data is safe.
        logger.error("Database migration failed (backup: %s)", exc.backup_path)
        _emit({"event": "fatal", "message": str(exc)})
        return 3
    for handler in logging.getLogger().handlers:
        handler.addFilter(SecretRedactionFilter(services.credentials))
    if restore is not None and restore["ok"]:
        # Nothing is being imported yet, so the folder of originals can be made to match.
        removed = services.sources.forget_unreferenced_files()
        logger.info("Removed %d stored files the restored data does not refer to", removed)
    app = create_app(services)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((LOOPBACK, args.port))
    except OSError as exc:
        services.close()
        _emit({"event": "fatal", "message": f"Could not bind a loopback port: {exc.strerror}"})
        return 2

    config = uvicorn.Config(
        app,
        log_config=None,
        access_log=False,
        server_header=False,
        date_header=False,
        timeout_graceful_shutdown=5,
    )
    server = uvicorn.Server(config)
    _watch_parent(server)
    logger.info("Starting adle-core %s", __version__)
    try:
        asyncio.run(_serve(server, sock, restore))
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        services.close()
    logger.info("adle-core stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
