"""Draft a list of concepts from the headings of a learner's own materials.

This is deliberately simple and makes no use of a language model: a syllabus or
set of notes usually names its topics in its headings, and those are a better
starting point than an empty page. The result is only ever a *suggestion*. The
learner chooses which candidates to keep, and nothing is inferred about which
concept depends on which; a heading order is not evidence of a prerequisite.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

MAX_CANDIDATES = 40
MIN_TITLE_LENGTH = 3
MAX_TITLE_LENGTH = 120

#: Headings that organise a document rather than name something to learn.
ADMINISTRATIVE_HEADINGS = frozenset(
    {
        "about this course",
        "acknowledgements",
        "acknowledgments",
        "assessment",
        "bibliography",
        "contact",
        "contents",
        "course information",
        "course outline",
        "course overview",
        "further reading",
        "grading",
        "index",
        "office hours",
        "overview",
        "policies",
        "reading list",
        "references",
        "resources",
        "schedule",
        "summary",
        "table of contents",
    }
)

#: What may follow a number: colon, full stop, bracket, hyphen, en dash, em dash.
_SEPARATOR = r"[:.)\-" + chr(0x2013) + chr(0x2014) + "]"

# "3.", "3.2", "3.2.1)", "Week 4:", "Unit 2 -", "Lecture 10.", "Part II:"
_NUMBERING = re.compile(
    rf"""^\s*
    (?:
        (?:week|unit|lecture|lesson|chapter|module|part|section|topic|session)
        \s+ (?:\d+|[ivxlc]+) \b \s* {_SEPARATOR}* \s*
      |
        \d+ (?:\.\d+)* \s* {_SEPARATOR}+ \s* (?!\d)
      |
        \d+ (?:\.\d+)+ \s+
    )""",
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class HeadingSection:
    """A headed section of an imported document, as stored at import time."""

    section_id: str
    source_id: str
    source_name: str
    title: str
    #: Heading depth: 0 for a document title, 1 for a top-level heading, and so on.
    level: int
    ordinal: int


@dataclass(frozen=True, slots=True)
class OutlineCandidate:
    #: The heading with any numbering removed.
    title: str
    section_id: str
    source_id: str
    source_name: str


def clean_title(heading: str) -> str:
    """Remove numbering such as "3.2" or "Week 4:" and tidy the spacing."""
    title = " ".join(heading.split())
    stripped = _NUMBERING.sub("", title, count=1).strip()
    # A heading that is nothing but its number ("Week 4") keeps its original text.
    return stripped.rstrip(" :.-") if len(stripped) >= MIN_TITLE_LENGTH else title


def _key(title: str) -> str:
    return title.casefold()


def _topic_level(sections: Sequence[HeadingSection]) -> int | None:
    """The heading depth whose headings most plausibly name the document's topics.

    A document often has one title above everything else. Its topics are then
    the headings one level down, not the title itself.
    """
    levels = sorted({section.level for section in sections})
    for level in levels:
        at_level = [section for section in sections if section.level == level]
        deeper_exists = level != levels[-1]
        if len(at_level) == 1 and deeper_exists:
            continue
        return level
    return levels[-1] if levels else None


def draft_outline(
    sections: Sequence[HeadingSection],
    existing_titles: Collection[str] = (),
    *,
    limit: int = MAX_CANDIDATES,
) -> list[OutlineCandidate]:
    """Candidate concepts, in the order the materials present them.

    ``sections`` are the headed sections of every source in the course, in
    reading order per source. Titles already used by a concept, repeated
    headings, and headings that only organise a document are left out.
    """
    taken = {_key(clean_title(title)) for title in existing_titles}
    candidates: list[OutlineCandidate] = []

    by_source: dict[str, list[HeadingSection]] = {}
    for section in sections:
        by_source.setdefault(section.source_id, []).append(section)

    for source_sections in by_source.values():
        ordered = sorted(source_sections, key=lambda section: section.ordinal)
        level = _topic_level(ordered)
        for section in ordered:
            if section.level != level:
                continue
            title = clean_title(section.title)
            key = _key(title)
            if (
                not MIN_TITLE_LENGTH <= len(title) <= MAX_TITLE_LENGTH
                or key in taken
                or key in ADMINISTRATIVE_HEADINGS
            ):
                continue
            taken.add(key)
            candidates.append(
                OutlineCandidate(
                    title=title,
                    section_id=section.section_id,
                    source_id=section.source_id,
                    source_name=section.source_name,
                )
            )
            if len(candidates) >= limit:
                return candidates
    return candidates
