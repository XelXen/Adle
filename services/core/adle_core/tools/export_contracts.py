"""Print the contracts of the core as JSON for `scripts/generate-contracts.mjs`.

Usage: ``python -m adle_core.tools.export_contracts``

The output is one JSON object with two members:

``openapi``
    The OpenAPI document of the real application object, so the TypeScript
    types and the renderer's operation allowlist can never drift from the
    routes that actually exist.

``lesson_ir``
    The JSON Schema of a lesson bundle (``lessons.ir.LessonBundle``): the form
    a lesson must have before it is stored, whoever wrote it.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from adle_core.api.app import create_app
from adle_core.api.auth import LaunchToken
from adle_core.application.services import build_services
from adle_core.config import Settings
from adle_core.lessons.ir import SCHEMA_VERSION, LessonBundle


def build_contract() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="adle-contract-") as scratch:
        services = build_services(
            Settings(data_dir=Path(scratch)),
            LaunchToken("contract-export-only-not-a-real-token"),
        )
        try:
            return create_app(services).openapi()
        finally:
            services.close()


def build_lesson_ir_schema() -> dict[str, Any]:
    """The Lesson IR as JSON Schema. Validation itself is always done by the Pydantic models."""
    schema = LessonBundle.model_json_schema()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **schema,
        "title": f"Adle Lesson IR {SCHEMA_VERSION}",
    }


def main() -> int:
    contracts = {"openapi": build_contract(), "lesson_ir": build_lesson_ir_schema()}
    json.dump(contracts, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
