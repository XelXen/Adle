"""Print the API contract as JSON for `scripts/generate-contracts.mjs`.

Usage: ``python -m adle_core.tools.export_contracts``

The output is the OpenAPI document of the real application object, so the
TypeScript types and the renderer's operation allowlist can never drift from
the routes that actually exist.
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


def main() -> int:
    json.dump(build_contract(), sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
