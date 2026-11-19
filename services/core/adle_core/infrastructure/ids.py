"""Identifier generation.

Identifiers are opaque, random, and prefixed with their kind so a stray id in
a log or a bug report is self-describing (``crs_…`` is a course, ``src_…`` a
source). They are stable for the life of the record.
"""

from __future__ import annotations

import re
import secrets
from typing import Final

_ID_PATTERN: Final = re.compile(r"^[a-z]{2,5}_[0-9a-f]{20}$")


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(10)}"


def is_id(value: str, prefix: str | None = None) -> bool:
    """True when ``value`` is a well-formed identifier (optionally of a given kind)."""
    if not _ID_PATTERN.match(value):
        return False
    return prefix is None or value.startswith(f"{prefix}_")
