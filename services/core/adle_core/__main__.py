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
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import socket
import sys
import threading
from typing import Any

import uvicorn

from adle_core import __version__
from adle_core.api.app import create_app
from adle_core.api.auth import LaunchToken
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


def _read_handshake() -> LaunchToken:
    """Read the launch token from the first line of stdin."""
    line = sys.stdin.readline()
    if not line:
        raise SettingsError("No launch handshake received on stdin.")
    try:
        payload: Any = json.loads(line)
        token = payload["token"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SettingsError("The launch handshake was malformed.") from exc
    if not isinstance(token, str):
        raise SettingsError("The launch handshake was malformed.")
    try:
        return LaunchToken(token)
    except ValueError as exc:
        raise SettingsError(str(exc)) from exc


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


async def _serve(server: uvicorn.Server, sock: socket.socket) -> None:
    async def announce_when_started() -> None:
        while not server.started:
            if server.should_exit:
                return
            await asyncio.sleep(0.01)
        _emit({"event": "ready", "port": sock.getsockname()[1], "version": __version__})

    announcer = asyncio.create_task(announce_when_started())
    try:
        await server.serve(sockets=[sock])
    finally:
        announcer.cancel()


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments[:1] == ["--parse-worker"]:
        # A packaged build has a single executable. Document parsing runs in a
        # child of the same executable, started with this flag (see ingestion/extract.py).
        from adle_core.ingestion import worker

        return worker.main()

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    try:
        settings = Settings.from_environment(args.data_dir)
        settings.ensure_directories()
        token = _read_handshake()
    except SettingsError as exc:
        _emit({"event": "fatal", "message": str(exc)})
        return 2

    try:
        services = build_services(settings, token)
    except MigrationError as exc:
        # The message is written for the learner and already says the data is safe.
        logger.error("Database migration failed (backup: %s)", exc.backup_path)
        _emit({"event": "fatal", "message": str(exc)})
        return 3
    for handler in logging.getLogger().handlers:
        handler.addFilter(SecretRedactionFilter(services.credentials))
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
        asyncio.run(_serve(server, sock))
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        services.close()
    logger.info("adle-core stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
