"""What a slide's trial said of its layout, as sentences for the model that mends it (ADR-073).

A slide (ADR-049) says as each step ends, in the player, how many of its words lie over
others or under a line, and which (``layout.py``'s ``audit``): "2 overlapping, 1 under a
line, 0 past the edge, 0 without a shadow; note over water; water under heat", each name a
key of the slide's elements ("nodes.3" is a piece of "nodes"). A slide that says so as it
is tried in the hidden frame is sent back to the model that wrote its script, told which of
its elements are in each other's way, and drawn again.

Pure. Only an element of the slide's own script is ever named back to the model: what a
scene says is never passed on as it is.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence

#: The most mends a slide is sent back for: one request each.
MAX_SLIDE_MENDS = 2
#: The most faults one request is told.
MAX_FAULTS = 6

_COUNTS = re.compile(r"^\s*(\d+) overlapping, (\d+) under a line, (\d+) past the edge")
_OVER = re.compile(r"^\s*([A-Za-z][\w./]{0,60}) over ([A-Za-z][\w./]{0,60})\s*$")
_UNDER = re.compile(r"^\s*([A-Za-z][\w./]{0,60}) under ([A-Za-z][\w./]{0,60})\s*$")


def _element(key: str, elements: Collection[str]) -> str | None:
    """The element of the script a key is part of: "nodes.3" is "nodes"; None for one the
    script does not have."""
    name = re.split(r"[./]", key, maxsplit=1)[0]
    return name if name in elements else None


def crowded(notes: Sequence[str]) -> bool:
    """Whether a slide said, at any step, that a word lies over another or under a line."""
    for note in notes:
        counts = _COUNTS.match(note)
        if counts is not None and (int(counts.group(1)) > 0 or int(counts.group(2)) > 0):
            return True
    return False


def faults(notes: Sequence[str], elements: Collection[str]) -> list[str]:
    """What is in whose way, a sentence each, by the names the script gave its elements.
    A slide that also lies past the edge says so once."""
    found: list[str] = []
    past = False
    for note in notes:
        counts = _COUNTS.match(note)
        if counts is not None and int(counts.group(3)) > 0:
            past = True
        for item in note.split(";")[1:]:
            over = _OVER.match(item)
            under = _UNDER.match(item)
            if over is not None:
                top, below = _element(over.group(1), elements), _element(over.group(2), elements)
                if top and below and top != below:
                    found.append(f'The words of "{top}" lie over the words of "{below}".')
                elif top and below:
                    found.append(f'Two of the words of "{top}" lie over each other.')
            elif under is not None:
                word, line = _element(under.group(1), elements), _element(under.group(2), elements)
                if word and line:
                    found.append(f'A line of "{line}" runs through the words of "{word}".')
    if past:
        found.append("Something lies past the edge of the screen.")
    return list(dict.fromkeys(found))[:MAX_FAULTS]


def weight(notes: Sequence[str]) -> int:
    """How crowded a slide was, all its steps together: the words over others and the words
    under a line, as it said at the end of each. A mended slide is kept when this is less."""
    total = 0
    for note in notes:
        counts = _COUNTS.match(note)
        if counts is not None:
            total += int(counts.group(1)) + int(counts.group(2))
    return total
