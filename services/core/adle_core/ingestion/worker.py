"""Parser worker process.

Run as ``python -m adle_core.ingestion.worker`` (or ``adle-core --parse-worker``
in a packaged build). It reads one JSON request from stdin, parses one
document, writes one JSON response to stdout, and exits.

This module must stay cheap to import: it is started once per imported file.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from adle_core.ingestion.parsers import parse_document
from adle_core.ingestion.types import (
    DocumentKind,
    ExtractedDocument,
    ExtractedSection,
    IngestionError,
    Limits,
    SectionKind,
)

CRASH_MESSAGE = "The file could not be read. It may be damaged."


def document_to_json(document: ExtractedDocument) -> dict[str, Any]:
    return {
        "kind": document.kind.value,
        "parser": document.parser,
        "parser_version": document.parser_version,
        "warnings": list(document.warnings),
        "picture_pages": list(document.picture_pages),
        "sections": [
            {
                "kind": section.kind.value,
                "text": section.text,
                "title": section.title,
                "page_number": section.page_number,
                "level": section.level,
                "confidence": section.confidence,
            }
            for section in document.sections
        ],
    }


def _optional(value: Any, expected: type) -> Any:
    if value is not None and not isinstance(value, expected):
        raise TypeError("unexpected field type")
    return value


def document_from_json(data: Any, limits: Limits) -> ExtractedDocument:
    """Rebuild a document from a worker's response, trusting nothing about its shape.

    The worker has just processed a possibly hostile file. Its output is plain
    JSON (never pickle, which could execute code here), and every field is
    type-checked and bounded before it is used.
    """
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise TypeError("malformed worker response")
    sections: list[ExtractedSection] = []
    total = 0
    for item in data["sections"]:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise TypeError("malformed section")
        total += len(item["text"])
        if total > limits.max_characters:
            raise IngestionError(
                "file_too_large", "The document contains more text than Adle can import at once."
            )
        confidence = item.get("confidence", 1.0)
        if not isinstance(confidence, int | float):
            raise TypeError("malformed confidence")
        title = _optional(item.get("title"), str)
        sections.append(
            ExtractedSection(
                kind=SectionKind(str(item.get("kind"))),
                text=item["text"],
                title=title[:300] if title else None,
                page_number=_optional(item.get("page_number"), int),
                level=_optional(item.get("level"), int),
                confidence=min(1.0, max(0.0, float(confidence))),
            )
        )
    warnings = data.get("warnings", [])
    if not isinstance(warnings, list) or not all(isinstance(entry, str) for entry in warnings):
        raise TypeError("malformed warnings")
    parser, parser_version = data.get("parser"), data.get("parser_version")
    if not isinstance(parser, str) or not isinstance(parser_version, str):
        raise TypeError("malformed parser identity")
    pictures = data.get("picture_pages", [])
    if (
        not isinstance(pictures, list)
        or len(pictures) > limits.max_pages
        or not all(
            isinstance(page, int) and not isinstance(page, bool) and 1 <= page <= limits.max_pages
            for page in pictures
        )
    ):
        raise TypeError("malformed picture pages")
    return ExtractedDocument(
        kind=DocumentKind(str(data.get("kind"))),
        sections=tuple(sections),
        parser=parser[:40],
        parser_version=parser_version[:40],
        warnings=tuple(entry[:500] for entry in warnings[:20]),
        picture_pages=tuple(sorted(set(pictures))),
    )


def handle(request: Any) -> dict[str, Any]:
    """Parse the document named by ``request``, or draw one of its pages, and say how it went."""
    if isinstance(request, dict) and "render_page" in request:
        return _render(request)
    try:
        path = Path(request["path"])
        kind = DocumentKind(request["kind"])
        limits = Limits(**request["limits"])
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "code": "malformed_document", "message": CRASH_MESSAGE}
    try:
        return {"ok": True, "document": document_to_json(parse_document(path, kind, limits))}
    except IngestionError as error:
        return {"ok": False, "code": error.code, "message": error.message}
    except MemoryError:
        return {
            "ok": False,
            "code": "file_too_large",
            "message": "The file is too large to read in memory.",
        }
    except Exception as error:
        # The exception text may quote the document, so only its type is reported.
        return {
            "ok": False,
            "code": "malformed_document",
            "message": f"{CRASH_MESSAGE} ({type(error).__name__})",
        }


def request_for(path: Path, kind: DocumentKind, limits: Limits) -> dict[str, Any]:
    return {"path": str(path), "kind": kind.value, "limits": asdict(limits)}


def render_request_for(path: Path, page: int) -> dict[str, Any]:
    return {"path": str(path), "render_page": page}


def _render(request: dict[str, Any]) -> dict[str, Any]:
    """Draw one page of a PDF as a picture (ADR-060)."""
    import base64

    from adle_core.ingestion.render import page_picture

    path, page = request.get("path"), request.get("render_page")
    if not isinstance(path, str) or not isinstance(page, int) or isinstance(page, bool):
        return {"ok": False, "code": "malformed_document", "message": CRASH_MESSAGE}
    try:
        picture = page_picture(Path(path), page)
    except IngestionError as error:
        return {"ok": False, "code": error.code, "message": error.message}
    except MemoryError:
        return {"ok": False, "code": "file_too_large", "message": "The page is too large to draw."}
    except Exception as error:
        return {
            "ok": False,
            "code": "malformed_document",
            "message": f"{CRASH_MESSAGE} ({type(error).__name__})",
        }
    return {"ok": True, "png": base64.b64encode(picture).decode("ascii")}


def main() -> int:
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        request = None
    payload = json.dumps(handle(request), ensure_ascii=True).encode("ascii")
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
