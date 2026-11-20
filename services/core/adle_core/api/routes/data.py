"""The learner's data as a whole.

Saving a copy is *internal*: only the Electron main process calls it, with a path the
learner chose in a save dialog of the operating system. It is excluded from the
renderer's operation allowlist (``x-adle-internal``), so nothing running in the page
can name a file to write. Restoring is not a route at all: the data cannot be replaced
under a running service, so it happens while the service starts (see ``__main__``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from adle_core.application.data_copy import save_copy
from adle_core.application.services import Services, get_services

router = APIRouter(prefix="/data", tags=["data"])

INTERNAL = {"x-adle-internal": True}
ServicesDep = Annotated[Services, Depends(get_services)]


class CopyDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Absolute path of the file to write, as the save dialog returned it.
    path: str = Field(min_length=1, max_length=4096, pattern=r"^[^\x00]+$")


@router.post(
    "/copy",
    operation_id="data.save_copy",
    status_code=204,
    openapi_extra=INTERNAL,
)
def save_a_copy(body: CopyDestination, services: ServicesDep) -> Response:
    save_copy(services.settings, Path(body.path))
    return Response(status_code=204)
