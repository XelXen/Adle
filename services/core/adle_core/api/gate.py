"""What every request passes before anything of it is read.

FastAPI reads and parses a request's body before it runs the dependency that checks the
launch token, and the server puts no limit on a body. Left at that, a process on this
computer without the token, or a page in a browser that found the loopback port, could
make the core hold any amount of data in memory before being turned away.

So this stands in front of the routes: without the token nothing is read, and nobody's
body may be larger than anything the app itself sends.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from starlette.exceptions import HTTPException

from adle_core.api.auth import LaunchToken

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
App = Callable[[Scope, Receive, Send], Awaitable[None]]

#: The largest body a request may carry. The app's own are a few kilobytes (the main process
#: refuses anything over one megabyte from the page before it gets here).
MAX_BODY_BYTES = 2 * 1024 * 1024

UNAUTHORISED = "This request is not authorised."
TOO_LARGE = "That request is too large."


def _header(scope: Scope, name: bytes) -> str:
    for key, value in scope.get("headers", ()):
        if key == name:
            return bytes(value).decode("latin-1")
    return ""


async def _refuse(send: Send, status: int, code: str, message: str) -> None:
    body = json.dumps({"error": {"code": code, "message": message}}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                # The connection is not reused: what was left unread is not read later either.
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class Gate:
    """Token first, then a bound on the body. A plain ASGI layer, ahead of all routing."""

    def __init__(
        self, app: App, *, token: LaunchToken, max_body_bytes: int = MAX_BODY_BYTES
    ) -> None:
        self._app = app
        self._token = token
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._app(scope, receive, send)
            return
        if scope["type"] != "http":
            # Nothing here speaks WebSocket; a connection of any other kind is refused.
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return

        scheme, _, presented = _header(scope, b"authorization").partition(" ")
        if scheme.lower() != "bearer" or not self._token.matches(presented.strip() or "-"):
            await _refuse(send, 401, "unauthorized", UNAUTHORISED)
            return

        declared = _header(scope, b"content-length")
        if declared:
            try:
                length = int(declared)
            except ValueError:
                await _refuse(send, 400, "invalid_request", "The request was not understood.")
                return
            if length > self._max_body_bytes:
                await _refuse(send, 413, "payload_too_large", TOO_LARGE)
                return

        seen = 0

        async def bounded() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self._max_body_bytes:
                    # An HTTPException is the one thing the framework passes on untouched
                    # while it is reading a body.
                    raise HTTPException(status_code=413, detail=TOO_LARGE)
            return message

        await self._app(scope, bounded, send)
