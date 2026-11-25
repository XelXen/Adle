"""The files Adle writes around a film's chapters (ADR-065). Pure.

A film is one chapter for each concept of a course, in the order they are learned. A model
writes each chapter as a scene file (``generation.prompts.film_chapter_request``); Adle
writes everything else: the voice the film is read in (which also shuts the network out of
the engine's process), the file that gives a chapter that voice so that it can be looked at
alone, the file that plays every chapter in turn as one film, the film's opening, and a
chapter told in words when a model's would not run. A model's file is never changed and
never joined to another: each chapter is a module of its own, so that one chapter's names
cannot touch another's, and each begins on an empty stage with the camera as it was.
"""

from __future__ import annotations

import json
import re
import textwrap
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from adle_core.film.policy import said, spoken_problem, text_problem

#: A chapter says at least this many lines, or it is not a chapter.
MIN_LINES = 8
#: How many times a chapter is sent back to be mended, told what was wrong with it.
MAX_MENDS = 3
#: The most chapters a film has.
MAX_CHAPTERS = 60
#: The most points a chapter told in words brings up, one at a time.
MAX_POINTS = 5

VOICE_MODULE = "adle_voice"
VOICE_INDEX = "voice.json"
FILM_MODULE = "film"
FILM_SCENE = "Film"
TAKE_SCENE = "Take"
CHAPTER_SCENE = "Chapter"


def chapter_module(index: int) -> str:
    return f"chapter_{index + 1:02d}"


def take_module(index: int) -> str:
    return f"take_{index + 1:02d}"


_FENCE = re.compile(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", re.DOTALL)


def written_file(answer: str) -> str:
    """The file in a model's answer: what is inside its fence if it put one round it, the
    longest if there are several, or else the answer itself."""
    fenced = _FENCE.findall(answer)
    chosen = max(fenced, key=len) if fenced else answer
    return chosen.strip() + "\n"


# -- the voice -------------------------------------------------------------------------------

_VOICE_SOURCE = '''"""Adle's: the voice a film is read in, and a door shut. A chapter never
imports this: the files that play a chapter do, before the chapter."""
import json
import socket
from pathlib import Path

import numpy as np
from manimgx.audio import Speech, Word


def _nothing_is_asked(*_arguments, **_keywords):
    raise OSError("A film is made on this computer: nothing is asked of the network.")


# The engine has a voice of its own that speaks through a service on the internet, which a
# scene without a voice would use. Every scene Adle plays has this voice instead; and should
# anything in this program reach for the network all the same, it is refused here.
socket.socket.connect = _nothing_is_asked
socket.socket.connect_ex = _nothing_is_asked
socket.create_connection = _nothing_is_asked
socket.getaddrinfo = _nothing_is_asked

_HERE = Path(__file__).resolve().parent
try:
    _SAID = json.loads((_HERE / "{index}").read_text(encoding="utf-8"))
except (OSError, ValueError):
    _SAID = {{}}


def voice(text: str) -> Speech:
    """A line as it was recorded on this computer, with when each word is said; or, for a
    line that was not, quiet for as long as it would take to say."""
    said = _SAID.get(" ".join(text.split()))
    if said:
        words = [Word(word, start, end) for word, start, end in said["words"]]
        return Speech((_HERE / said["clip"]).read_bytes(), text=text, words=words)
    count = max(1, len(text.split()))
    seconds = max(1.2, count / {pace})
    return Speech(np.zeros(int(24000 * seconds), dtype=np.float32), text=text, rate=24000)
'''

#: How many words a second a line is given when nobody has recorded it.
QUIET_WORDS_A_SECOND = 2.6


def voice_source() -> str:
    return _VOICE_SOURCE.format(index=VOICE_INDEX, pace=QUIET_WORDS_A_SECOND)


def spoken_key(script: str) -> str:
    """What a line of a chapter is recorded as and looked up by: the words the engine says,
    without the brackets that time its animations, one space between them."""
    return said(script)


_RUN = re.compile(r"\S+")


def engine_words(
    text: str, words: Sequence[Mapping[str, float | int]], seconds: float
) -> list[tuple[str, float, float]]:
    """A recorded line's words as the film engine reads them: one for every run of
    characters between spaces, in order, each with when it is said.

    Adle's voice says when it said each word it spoke, by the word's place in the line. The
    engine finds a bracketed word by counting runs, so there must be exactly one time for
    each run: a run made of several spoken words takes all of them, and one the voice did
    not time (a dash, a sign) takes the gap it stands in. Times never go backwards and never
    pass the end of the recording.
    """
    runs = [(found.start(), found.end(), found.group()) for found in _RUN.finditer(text)]
    timed: list[tuple[float, float] | None] = []
    for begin, end, _ in runs:
        inside = [
            word
            for word in words
            if int(word["index"]) < end and int(word["index"]) + int(word["length"]) > begin
        ]
        timed.append(
            (
                min(float(word["start"]) for word in inside),
                max(float(word["end"]) for word in inside),
            )
            if inside
            else None
        )
    whole = max(0.0, float(seconds))
    found_words: list[tuple[str, float, float]] = []
    reached = 0.0
    for position, (_, _, run) in enumerate(runs):
        span = timed[position]
        if span is None:
            following = next((later for later in timed[position + 1 :] if later), None)
            span = (reached, following[0] if following else whole)
        start = min(max(span[0], reached), whole)
        stop = min(max(span[1], start), whole)
        found_words.append((run, round(start, 3), round(stop, 3)))
        reached = stop
    return found_words


# -- a chapter alone, and the whole film -------------------------------------------------------


def take_source(index: int) -> str:
    """One chapter by itself, with the film's voice: what the engine is given to look at."""
    module = chapter_module(index)
    return (
        '"""Adle\'s: one chapter by itself, to be looked at before it joins the film."""\n'
        f"import {VOICE_MODULE}\n"
        f"import {module}\n\n\n"
        f"class {TAKE_SCENE}({module}.{CHAPTER_SCENE}):\n"
        f"    voice = {VOICE_MODULE}.voice\n"
    )


def film_source(titles: Sequence[str]) -> str:
    """The whole film: every chapter in turn, on one stage. A chapter is run as it was
    written: the methods it gave its own scene are lent to the film's for as long as the
    chapter lasts. Each begins as it did when it was looked at alone: what the one before
    left on the stage, in front of it, running on it, or done to the camera is gone."""
    imports = "\n".join(f"import {chapter_module(index)}" for index in range(len(titles)))
    chapters = "\n".join(
        f"    ({chapter_module(index)}.{CHAPTER_SCENE}, {json.dumps(title)}),"
        for index, title in enumerate(titles)
    )
    return (
        '"""Adle\'s: the whole film, a chapter at a time."""\n'
        "import manimgx as m\n\n"
        f"import {VOICE_MODULE}\n"
        f"{imports}\n\n"
        f"CHAPTERS = [\n{chapters}\n]\n\n\n"
        f"class {FILM_SCENE}(m.Scene):\n"
        f"    voice = {VOICE_MODULE}.voice\n\n"
        "    def construct(self):\n"
        "        for chapter, title in CHAPTERS:\n"
        "            lent = [\n"
        "                name\n"
        "                for name, value in vars(chapter).items()\n"
        '                if callable(value) and not name.startswith("_") and name != "construct"\n'
        "            ]\n"
        "            for name in lent:\n"
        "                setattr(self, name, getattr(chapter, name).__get__(self))\n"
        "            self.next_section(title)\n"
        "            chapter.construct(self)\n"
        "            for name in lent:\n"
        "                delattr(self, name)\n"
        "            self.updaters = []\n"
        "            left = [*self.mobjects, *self.foreground_mobjects]\n"
        "            for thing in left:\n"
        "                thing.clear_updaters()\n"
        "            if left:\n"
        "                self.play(m.FadeOut(m.Group(*left)), run_time=0.6)\n"
        "            self.clear()\n"
        "            self.camera = m.Camera()\n"
        "            self.wait(0.4)\n"
    )


# -- a chapter in words ----------------------------------------------------------------------

_NOT_SPOKEN = re.compile(r"https?://\S+|[\[\]$\\<>{}`#|^_~*]")


def spoken(text: str, limit: int = 300) -> str:
    """Words from the course as a line a voice can say: no brackets, no notation, one line;
    or nothing, where what is left still could not be said."""
    plain = " ".join(_NOT_SPOKEN.sub(" ", text).split())[:limit].rstrip()
    if not plain or spoken_problem(plain) or text_problem(plain):
        return ""
    return plain


def _shown(text: str, width: int = 44, lines: int = 3) -> list[str]:
    """Words from the course as lines that fit on the stage, each one a chapter may hold."""
    plain = " ".join(_NOT_SPOKEN.sub(" ", text).split())
    rows = [row for row in textwrap.wrap(plain, width=width)[:lines] if not text_problem(row)]
    return rows or [""]


@dataclass(frozen=True, slots=True)
class PlainChapter:
    source: str
    #: What it says, a line at a time.
    lines: tuple[str, ...]


def plain_chapter(title: str, points: Sequence[str], opening: str | None = None) -> PlainChapter:
    """A chapter in words, written by Adle: its title, and its points brought up one at a
    time as each is said. What a film opens with, and what it falls back on when a model's
    chapter would not run. What the course says is put into it only as quoted text."""
    first = spoken(opening or f"Next: {title}.") or "Next, a new chapter."
    lines = [first]
    heading = _shown(title, 40, 1)[0] or "Next chapter"
    body = [
        f"        title = m.Text({json.dumps(heading)}, font_size=44)",
        "        title.to_edge(m.UP, buff=0.5)",
        f"        self.say({json.dumps(first)}, m.Write(title))",
        "        rows = m.VGroup()",
    ]
    for point in list(points)[:MAX_POINTS]:
        line = spoken(point)
        shown = [row for row in _shown(point) if row]
        if not line or not shown:
            continue
        lines.append(line)
        texts = ", ".join(f"m.Text({json.dumps(row)}, font_size=30)" for row in shown)
        body += [
            f"        row = m.VGroup({texts}).arrange(m.DOWN, aligned_edge=m.LEFT, buff=0.15)",
            "        rows.add(row)",
            "        rows.arrange(m.DOWN, aligned_edge=m.LEFT, buff=0.45).move_to([0, -0.4, 0])",
            f"        self.say({json.dumps(line)}, m.FadeIn(row))",
        ]
    body.append("        self.wait(0.6)")
    source = (
        '"""Adle\'s: a chapter in words."""\n'
        "import manimgx as m\n\n\n"
        f"class {CHAPTER_SCENE}(m.Scene):\n"
        "    def construct(self):\n" + "\n".join(body) + "\n"
    )
    return PlainChapter(source=source, lines=tuple(lines))


def opening_points(titles: Sequence[str]) -> list[str]:
    """What a film says it is about to cover: its chapters, a few to a line."""
    if len(titles) <= MAX_POINTS:
        return list(titles)
    size = -(-len(titles) // MAX_POINTS)
    return [", ".join(titles[start : start + size]) for start in range(0, len(titles), size)]


# -- the words of a film, as it was rendered ---------------------------------------------------

_TIME = re.compile(r"(\d+):(\d\d):(\d\d)[,.](\d{3})\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d{3})")
#: The most cues read from one film's subtitles, and the longest a cue's words may be.
MAX_CUES = 20_000
MAX_CUE_CHARACTERS = 400


def captions(srt: str, limit: int = MAX_CUES) -> list[tuple[float, float, str]]:
    """The subtitles the engine wrote beside a video, as when each is shown and what it
    says."""
    found: list[tuple[float, float, str]] = []
    for block in re.split(r"\r?\n\s*\r?\n", srt):
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        for position, line in enumerate(lines):
            timed = _TIME.match(line)
            if not timed:
                continue
            numbers = [int(part) for part in timed.groups()]
            start = numbers[0] * 3600 + numbers[1] * 60 + numbers[2] + numbers[3] / 1000
            end = numbers[4] * 3600 + numbers[5] * 60 + numbers[6] + numbers[7] / 1000
            text = " ".join(lines[position + 1 :])
            if text and end > start:
                found.append((round(start, 3), round(end, 3), text[:MAX_CUE_CHARACTERS]))
            break
        if len(found) >= limit:
            break
    return found
