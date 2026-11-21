"""Run a parser in a separate process, with a time limit.

Document parsers handle hostile and malformed input. A damaged PDF can send a
parser into a long loop or exhaust memory. Running the parse in a child
process means it can be stopped: on timeout the child is killed and the
import fails cleanly, while the service stays responsive.

The child is started with ``subprocess`` and explicit standard streams, never
with ``multiprocessing``. This matters on Windows: the service keeps a thread
blocked reading its own stdin (to notice when the desktop app goes away), and
a child that inherits that stdin handle hangs during interpreter start-up.
Giving the child its own pipes avoids the shared handle entirely. The reply
is JSON rather than pickle, so a parser process that was subverted by a
hostile file cannot run code in the service by crafting its answer.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from adle_core.ingestion.detect import detect_kind
from adle_core.ingestion.parsers import parse_document
from adle_core.ingestion.types import DEFAULT_LIMITS, ExtractedDocument, IngestionError, Limits
from adle_core.ingestion.worker import CRASH_MESSAGE, document_from_json, request_for

#: The signature of an extraction function. Tests can substitute an in-process one.
Extractor = Callable[[Path, str, Limits], ExtractedDocument]

_TIMEOUT_MESSAGE = (
    "Reading this file took too long, so the import was stopped. "
    "The file may be damaged; try exporting it again or splitting it into parts."
)
#: Upper bound on a worker's reply, as a guard against a runaway child.
_MAX_REPLY_BYTES = 64 * 1024 * 1024


def interpreter_flags() -> list[str]:
    """Flags this interpreter runs with that a child of it must run with too.

    A packaged build starts its private Python isolated from the computer it is on:
    no ``PYTHON*`` variables, no user site-packages, nothing from the current folder
    (ADR-019). A worker started from it without the same flag would be open to all
    three, and it is the worker that reads files from elsewhere.
    """
    flags: list[str] = []
    if sys.flags.isolated:
        flags.append("-I")
    if sys.flags.utf8_mode:
        flags.extend(["-X", "utf8"])
    return flags


def worker_command() -> list[str]:
    """How to start the parser worker: the same interpreter, the same isolation."""
    return [sys.executable, *interpreter_flags(), "-m", "adle_core.ingestion.worker"]


def extract_in_process(
    path: Path, display_name: str, limits: Limits = DEFAULT_LIMITS
) -> ExtractedDocument:
    """Detect and parse in the calling process. For tests and trusted, tiny inputs only."""
    return parse_document(path, detect_kind(path, display_name, limits), limits)


def extract_isolated(
    path: Path, display_name: str, limits: Limits = DEFAULT_LIMITS
) -> ExtractedDocument:
    """Detect the file type, then parse it in a killable child process."""
    kind = detect_kind(path, display_name, limits)
    request = json.dumps(request_for(path, kind, limits)).encode("utf-8")

    process = subprocess.Popen(  # noqa: S603 - fixed command; the path travels as data on stdin
        worker_command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        # No console window flashes up in a packaged Windows build.
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        reply, _ = process.communicate(request, timeout=limits.parse_timeout_seconds)
    except subprocess.TimeoutExpired as error:
        process.kill()
        process.communicate()
        raise IngestionError("parse_timeout", _TIMEOUT_MESSAGE) from error

    if process.returncode != 0 or not reply or len(reply) > _MAX_REPLY_BYTES:
        # The child died without a usable answer (crash, or killed by the OS for memory).
        raise IngestionError("malformed_document", CRASH_MESSAGE)
    try:
        response = json.loads(reply)
        if response.get("ok") is True:
            return document_from_json(response["document"], limits)
        code, message = response["code"], response["message"]
        if not isinstance(code, str) or not isinstance(message, str):
            raise TypeError("malformed error")
    except IngestionError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise IngestionError("malformed_document", CRASH_MESSAGE) from error
    raise _refusal(code, message)


#: Every reason a parser gives for not reading a file. A reply with any other is not one a
#: parser of ours wrote.
_REFUSALS = frozenset(
    {
        "empty_document",
        "encrypted_document",
        "file_too_large",
        "file_unreadable",
        "malformed_document",
        "scanned_document",
        "unsupported_type",
    }
)
_MAX_REFUSAL_CHARACTERS = 600
#: Control characters, and the characters that reorder or hide text.
_UNPRINTABLE = re.compile("[\u0000-\u001f\u007f-\u009f​-‏‪-‮⁦-⁩]")


def _refusal(code: str, message: str) -> IngestionError:
    """What a worker said about a file it would not read, made fit to show.

    The worker read a file from elsewhere, and what it says is shown to the learner. So
    its reason must be one a parser has, and its sentence is one plain line of limited
    length, whatever was sent. Anything else is treated as a worker that broke.
    """
    one_line = " ".join(_UNPRINTABLE.sub(" ", message).split())
    if code not in _REFUSALS or not one_line:
        return IngestionError("malformed_document", CRASH_MESSAGE)
    return IngestionError(code, one_line[:_MAX_REFUSAL_CHARACTERS])
