"""A chapter's storyboard, looked over by a model that sees pictures (ADR-066).

ManimGX's ``inspect`` draws the screen at the end of every animation of a scene, captioned
with the animation's number, its time and its line of the file, six pictures to a sheet,
beside the scene: ``<Scene>.storyboard.png``, then ``<Scene>.storyboard-2.png`` and on. The
sheets are sent with what is said while each animation plays to a model that reads
pictures. Its answer, a line for each fault, named by the number of the picture, is read
here into what the chapter's writer is told, by the line of the writer's own file.

Pure, but for reading and removing the sheets the engine wrote. What the model answers is
its own text about a chapter a model wrote: it is told to that chapter's writer and to
nobody else, and never logged.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from adle_core.film.policy import said
from adle_core.film.report import Report

#: The most sheets sent: 48 pictures, which no chapter of three or four minutes reaches
#: (one of 205 s had 31 animations and four sheets, 2026-11-25).
MAX_SHEETS = 8
#: The most one sheet may weigh. The engine's were 140 to 200 KB.
MAX_SHEET_BYTES = 4 * 1024 * 1024
#: The most animations whose words are told with the pictures.
MAX_TOLD = 120
#: The most of a line's words told with its picture.
MAX_SAID_CHARACTERS = 300
#: The most faults told to the writer, and the most of each.
MAX_SEEN = 8
MAX_SEEN_CHARACTERS = 300
#: What the model writes when it sees nothing wrong.
NOTHING = "NOTHING"

_PNG = b"\x89PNG\r\n\x1a\n"
_SHEET = re.compile(
    r"(?P<scene>[A-Za-z_][A-Za-z0-9_]*)\.storyboard(?:-(?P<number>[1-9]\d{0,2}))?\.png"
)
#: A fault as the model writes it: "#13: the arrow …", or "Picture 13: …", in a list or
#: not. A number alone is a list's, not a picture's.
_FAULT = re.compile(
    r"^\s*(?:[-*•]|\d{1,2}[.)])?\s*(?:#|picture\s+#?)\s*(\d{1,4})\s*"
    r"[:.)–—-]\s*(.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Told:
    """What is said while one animation plays, told beside its picture."""

    index: int
    start: float
    end: float
    #: Its words, as they are spoken; empty for an animation with none.
    said: str


def _sheets_of(folder: Path, scene: str) -> list[tuple[int, Path]]:
    found: list[tuple[int, Path]] = []
    try:
        entries = list(folder.iterdir())
    except OSError:
        return []
    for path in entries:
        match = _SHEET.fullmatch(path.name)
        if match is None or match.group("scene") != scene:
            continue
        found.append((int(match.group("number") or 1), path))
    return sorted(found)


def clear_sheets(folder: Path, scene: str) -> None:
    """Remove the sheets an earlier run left beside a scene, so that the ones there after
    the next run are that run's alone."""
    for _, path in _sheets_of(folder, scene):
        path.unlink(missing_ok=True)


def sheets(folder: Path, scene: str) -> list[bytes]:
    """The sheets of a scene's storyboard, in order: at most ``MAX_SHEETS``, each a PNG of
    at most ``MAX_SHEET_BYTES``. They stop at the first that is missing from the run of
    numbers, is not a plain file, is too large, or is not a PNG: what follows it would be
    numbered wrongly to whoever looks at them."""
    pictures: list[bytes] = []
    for expected, (number, path) in enumerate(_sheets_of(folder, scene)[:MAX_SHEETS], 1):
        if number != expected or path.is_symlink() or not path.is_file():
            break
        try:
            if path.stat().st_size > MAX_SHEET_BYTES:
                break
            data = path.read_bytes()
        except OSError:
            break
        if len(data) > MAX_SHEET_BYTES or not data.startswith(_PNG):
            break
        pictures.append(data)
    return pictures


def _said_by_line(source: str) -> list[tuple[int, int, str]]:
    """Each line a chapter says, with the lines of its file the call to say it spans."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return []
    found: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "say"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.append((node.lineno, node.end_lineno or node.lineno, said(node.args[0].value)))
    return found


def told(report: Report, source: str, chapter: str) -> list[Told]:
    """What is said while each animation of a chapter plays, in order, from the engine's
    report and the chapter's file (``chapter`` is its file's name, as the report names
    it). An animation of Adle's own files around the chapter, or one that says nothing,
    has no words."""
    spans = _said_by_line(source)

    def at(line: int) -> str:
        for first, last, text in spans:
            if first <= line <= last:
                return text
        return ""

    return [
        Told(
            index=play.index,
            start=play.start,
            end=play.end,
            said=at(play.line)[:MAX_SAID_CHARACTERS] if play.file == chapter else "",
        )
        for play in report.plays[:MAX_TOLD]
    ]


def seen(answer: str, report: Report, chapter: str) -> list[str]:
    """What the model saw wrong, a sentence each for the chapter's writer: by the line of
    the writer's own file that played the animation, and when its picture is on the screen.
    "NOTHING", or an answer with no line that names a picture, is nothing seen."""
    plays = {play.index: play for play in report.plays}
    found: list[str] = []
    for raw in answer.splitlines():
        match = _FAULT.match(raw.replace("**", ""))
        if match is None:
            continue
        what = " ".join(match.group(2).split())
        if not what or what.upper().strip(".") == NOTHING:
            continue
        play = plays.get(int(match.group(1)))
        if play is None:
            where = "in one of the pictures"
        elif play.file == chapter:
            where = f"line {play.line}, in the picture at {play.end:.1f} s"
        else:
            where = f"in the picture at {play.end:.1f} s"
        item = f"{where}: {what}"[:MAX_SEEN_CHARACTERS]
        if item not in found:
            found.append(item)
        if len(found) == MAX_SEEN:
            break
    return found
