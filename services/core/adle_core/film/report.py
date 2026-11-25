"""What the film engine said about a scene, read into data (ADR-065). Pure.

ManimGX's ``inspect`` runs a scene without making a video and prints three things: each
play with the line of the file it came from, problems of layout (words over words, a line
through a word, something past the edge of the frame, text too small to read), and, if the
scene stops, where and why. ``render`` prints the same after it has made the video. What it
prints is read as the pinned engine prints it (``catalog.ENGINE_VERSION``).

What is read here is told to the model that wrote the scene, so that it can mend it, and to
nobody else: it holds names and words out of the scene, which is the model's own text. It
is never logged.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

#: The most that is told to a writer about one scene.
MAX_FINDINGS = 14
MAX_FINDING_CHARACTERS = 300


@dataclass(frozen=True, slots=True)
class Play:
    index: int
    start: float
    end: float
    file: str
    line: int
    what: str


@dataclass(frozen=True, slots=True)
class Problem:
    file: str
    line: int
    #: When it is first seen, in seconds.
    start: float
    #: What is wrong, as the engine says it: what, and how.
    text: str


@dataclass(frozen=True, slots=True)
class Failure:
    """The scene stopped."""

    file: str | None
    line: int | None
    #: The kind of error and what it says, on one line.
    text: str
    #: What the engine suggests, when it does ("ShowCreation is Create in ManimGX").
    hint: str = ""


@dataclass(frozen=True, slots=True)
class Report:
    #: How long the scene is, when it ran to its end.
    seconds: float | None
    plays: tuple[Play, ...]
    problems: tuple[Problem, ...]
    failure: Failure | None

    @property
    def ran(self) -> bool:
        """It ran to its end: there is a length, and it did not stop."""
        return self.seconds is not None and self.failure is None

    @property
    def clean(self) -> bool:
        return self.ran and not self.problems


_HEAD = re.compile(r"^\S+\.py: \w+, ([0-9.]+) s, \d+ plays?\s*$")
#: What ``render`` says first, once the video is made: its file, length, size and rate.
_RENDERED = re.compile(r"^\S+\.mp4\s+([0-9.]+) s, \d+x\d+ at [0-9.]+ fps\b")
_PLAY = re.compile(r"^\s*#(\d+)\s+([0-9.]+)\D+?([0-9.]+)s\s+(\S+?\.py):(\d+)\s+(.*)$")
_PROBLEM = re.compile(r"^\s*\[\d+\]\s+t=([0-9.]+)(?:\D+?[0-9.]+)?s\s+\((\S+?\.py):(\d+)\)\s+(.*)$")
_WHERE = re.compile(r"^(\S+?\.py):(\d+): in \w+\s*$")
_ERROR = re.compile(
    r"^([A-Z][A-Za-z0-9_.]*(?:Error|Exception|Mistake|Warning|Interrupt)\w*): ?(.*)$"
)
_HINT = re.compile(r"^hint: (.*)$")
_SMALL = re.compile(r"text is \d+ px tall")
_QUOTED = re.compile(r"'((?:[^'\\]|\\.)*)'")


def _is_a_sign(text: str) -> bool:
    """Whether a problem is about text that is only a sign ("=", "+"): a sign is short by
    nature, and the engine's measure of text too small to read does not apply to it."""
    if not _SMALL.search(text):
        return False
    quoted = _QUOTED.findall(text)
    return bool(quoted) and not any(re.search(r"[A-Za-z0-9]", item) for item in quoted)


def read_report(out: str, err: str = "") -> Report:
    """Read what ``inspect`` or ``render`` printed: what it played, and what it said was
    wrong."""
    seconds: float | None = None
    plays: list[Play] = []
    problems: list[Problem] = []
    for line in out.splitlines():
        head = _HEAD.match(line) or _RENDERED.match(line)
        if head:
            seconds = float(head.group(1))
            continue
        play = _PLAY.match(line)
        if play:
            plays.append(
                Play(
                    index=int(play.group(1)),
                    start=float(play.group(2)),
                    end=float(play.group(3)),
                    file=play.group(4),
                    line=int(play.group(5)),
                    what=play.group(6).strip(),
                )
            )
            continue
        problem = _PROBLEM.match(line)
        if problem and not _is_a_sign(problem.group(4)):
            problems.append(
                Problem(
                    file=problem.group(2),
                    line=int(problem.group(3)),
                    start=float(problem.group(1)),
                    text=problem.group(4).strip(),
                )
            )
    return Report(
        seconds=seconds,
        plays=tuple(plays),
        problems=tuple(problems),
        failure=_failure(err) or (_failure(out) if seconds is None else None),
    )


def _failure(text: str) -> Failure | None:
    file: str | None = None
    line: int | None = None
    said = ""
    hint = ""
    for raw in text.splitlines():
        where = _WHERE.match(raw.strip())
        if where and file is None:
            file, line = where.group(1), int(where.group(2))
            continue
        error = _ERROR.match(raw.strip())
        if error:
            said = f"{error.group(1)}: {error.group(2)}".strip().rstrip(":")
            continue
        found = _HINT.match(raw.strip())
        if found:
            hint = found.group(1).strip()
    if not said and file is None:
        return None
    return Failure(file=file, line=line, text=said or "The scene stopped.", hint=hint)


def findings(report: Report, chapter: str) -> list[str]:
    """What to tell whoever wrote a chapter, a sentence each: where it stopped, or what is
    wrong with its layout, by the line of their own file. Lines of Adle's own files around
    the chapter are not named."""
    told: list[str] = []
    failure = report.failure
    if failure is not None:
        where = f"line {failure.line}: " if failure.file == chapter and failure.line else ""
        hint = f" ({failure.hint})" if failure.hint else ""
        told.append(f"{where}the scene stopped here. {failure.text}{hint}")
    seen: set[tuple[int, str]] = set()
    for problem in report.problems:
        key = (problem.line, problem.text)
        if key in seen:
            continue
        seen.add(key)
        where = f"line {problem.line}" if problem.file == chapter else "the scene"
        told.append(f"{where}, at {problem.start:.1f} s: {problem.text}")
    return [item[:MAX_FINDING_CHARACTERS] for item in told[:MAX_FINDINGS]]


def chapter_starts(report: Report, files: Sequence[str]) -> dict[str, float]:
    """When each chapter of a film begins, from the first play that came from its file."""
    starts: dict[str, float] = {}
    wanted = set(files)
    for play in report.plays:
        if play.file in wanted and play.file not in starts:
            starts[play.file] = play.start
    return starts
