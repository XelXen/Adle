"""Split extracted sections into retrievable passages.

Chunks follow the document's own structure: they never cross a section
boundary (a page or a headed section), they break at paragraph ends where
possible and at sentence ends otherwise, and each records its exact position
so a passage can always be traced back to where it came from.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from adle_core.ingestion.types import ExtractedSection

TARGET_CHARACTERS = 1_200
MAX_CHARACTERS = 1_800

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+")


@dataclass(frozen=True, slots=True)
class Chunk:
    #: Index of the section this chunk belongs to.
    section_index: int
    text: str
    #: Offsets into the section's text. ``section.text[char_start:char_end]`` contains the chunk.
    char_start: int
    char_end: int

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _spans(text: str, separator: re.Pattern[str]) -> list[tuple[int, int]]:
    """Non-empty pieces of ``text`` between matches of ``separator``, as (start, end) offsets."""
    spans: list[tuple[int, int]] = []
    start = 0
    for match in separator.finditer(text):
        if match.start() > start:
            spans.append((start, match.start()))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def _split_oversized(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Break one long paragraph at sentence ends, then at hard limits if it has none."""
    pieces: list[tuple[int, int]] = []
    for sentence_start, sentence_end in _spans(text[start:end], _SENTENCE_END):
        absolute_start, absolute_end = start + sentence_start, start + sentence_end
        while absolute_end - absolute_start > MAX_CHARACTERS:
            # No sentence boundary to use: cut at the last space before the limit.
            cut = text.rfind(" ", absolute_start, absolute_start + MAX_CHARACTERS)
            if cut <= absolute_start:
                cut = absolute_start + MAX_CHARACTERS
            pieces.append((absolute_start, cut))
            absolute_start = cut + 1 if text[cut : cut + 1] == " " else cut
        if absolute_end > absolute_start:
            pieces.append((absolute_start, absolute_end))
    return pieces


def chunk_section(section_index: int, text: str) -> list[Chunk]:
    """Chunk one section's text. Deterministic for a given input."""
    units: list[tuple[int, int]] = []
    for start, end in _spans(text, _PARAGRAPH_BREAK):
        if end - start > MAX_CHARACTERS:
            units.extend(_split_oversized(text, start, end))
        else:
            units.append((start, end))

    chunks: list[Chunk] = []
    current_start: int | None = None
    current_end = 0
    for start, end in units:
        if current_start is None:
            current_start, current_end = start, end
            continue
        would_be = end - current_start
        if would_be <= TARGET_CHARACTERS or (
            current_end - current_start < TARGET_CHARACTERS // 3 and would_be <= MAX_CHARACTERS
        ):
            current_end = end
        else:
            chunks.append(_make(section_index, text, current_start, current_end))
            current_start, current_end = start, end
    if current_start is not None:
        chunks.append(_make(section_index, text, current_start, current_end))
    return chunks


def _make(section_index: int, text: str, start: int, end: int) -> Chunk:
    return Chunk(
        section_index=section_index, text=text[start:end].strip(), char_start=start, char_end=end
    )


def chunk_document(sections: tuple[ExtractedSection, ...]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for index, section in enumerate(sections):
        chunks.extend(chunk for chunk in chunk_section(index, section.text) if chunk.text)
    return chunks
