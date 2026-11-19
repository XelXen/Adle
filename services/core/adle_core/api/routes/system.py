"""Service health and identity."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from adle_core import __version__

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: str
    version: str
    api_version: str


@router.get("/health", operation_id="system.health", response_model=Health)
def health() -> Health:
    """Liveness check used by the desktop shell after the ready handshake."""
    return Health(status="ok", version=__version__, api_version="v1")
