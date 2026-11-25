"""FastAPI application factory."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from adle_core import __version__
from adle_core.api.auth import require_launch_token
from adle_core.api.errors import ErrorResponse, install_error_handlers
from adle_core.api.gate import Gate
from adle_core.api.routes import (
    course_files,
    courses,
    curriculum,
    data,
    films,
    generation,
    learning,
    lessons,
    provider,
    settings_file,
    system,
    voice,
)
from adle_core.application.services import Services

API_PREFIX = "/v1"

# The service only ever answers on loopback. Rejecting other Host headers closes
# the DNS-rebinding route even before the token check.
_ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


def create_app(services: Services) -> FastAPI:
    """Build the API. The launch token gates every route; there are no public endpoints."""
    app = FastAPI(
        title="Adle core",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        separate_input_output_schemas=False,
        dependencies=[Depends(require_launch_token)],
        responses={
            401: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )
    app.state.services = services
    app.state.launch_token = services.launch_token

    # The last one added is the first a request meets: the Host header, then the token and
    # the size of the body (before any of the body is read), then the routes.
    app.add_middleware(Gate, token=services.launch_token)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_ALLOWED_HOSTS)
    install_error_handlers(app)

    for module in (
        system,
        provider,
        courses,
        course_files,
        curriculum,
        lessons,
        generation,
        learning,
        data,
        voice,
        settings_file,
        films,
    ):
        app.include_router(module.router, prefix=API_PREFIX)
    return app
