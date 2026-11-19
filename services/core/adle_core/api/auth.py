"""Authentication for the loopback API.

The Electron main process generates a random token for each launch and hands it
to this process over stdin. Every request must present it as a bearer token.
The token never appears in process arguments, the environment, or logs.
"""

from __future__ import annotations

import secrets

from fastapi import Request

from adle_core.errors import UnauthorizedError

MIN_TOKEN_LENGTH = 32


class LaunchToken:
    """Holds the per-launch token and checks presented credentials in constant time."""

    def __init__(self, value: str) -> None:
        if len(value) < MIN_TOKEN_LENGTH:
            raise ValueError("The launch token is too short to be safe.")
        self._value = value.encode("utf-8")

    def matches(self, presented: str) -> bool:
        return secrets.compare_digest(self._value, presented.encode("utf-8"))

    def __repr__(self) -> str:  # Never let the token leak through a repr or traceback.
        return "LaunchToken(<redacted>)"


def require_launch_token(request: Request) -> None:
    """FastAPI dependency: reject any request without the launch token."""
    token: LaunchToken = request.app.state.launch_token
    header = request.headers.get("authorization", "")
    scheme, _, presented = header.partition(" ")
    if scheme.lower() != "bearer" or not presented or not token.matches(presented.strip()):
        raise UnauthorizedError("This request is not authorised.")
