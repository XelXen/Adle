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
from manimgx.audio.sound import RATE


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


def _breath(text: str) -> float:
    """How long a line rests before the next one: lines are recorded one at a time, and
    played end to end they ran into each other. Longer after a sentence than a clause."""
    end = text.rstrip().rstrip({closing})[-1:]
    return {sentence} if end in {stops} else {clause}


def voice(text: str) -> Speech:
    """A line as it was recorded on this computer, with when each word is said, and a breath
    after it; or, for a line that was not, quiet for as long as it would take to say."""
    said = _SAID.get(" ".join(text.split()))
    rest = _breath(text)
    if said:
        words = [Word(word, start, end) for word, start, end in said["words"]]
        heard = Speech((_HERE / said["clip"]).read_bytes(), text=text, words=words).samples
        quiet = np.zeros((int(RATE * rest), *heard.shape[1:]), dtype=heard.dtype)
        return Speech(np.concatenate([heard, quiet]), text=text, words=words, rate=RATE)
    count = max(1, len(text.split()))
    seconds = max(1.2, count / {pace}) + rest
    return Speech(np.zeros(int(RATE * seconds), dtype=np.float32), text=text, rate=RATE)
'''

#: How many words a second a line is given when nobody has recorded it.
QUIET_WORDS_A_SECOND = 2.6
#: The rest after a line of the film's voice, in seconds (ADR-079): after a sentence,
#: and after a clause.
SENTENCE_REST = 0.45
CLAUSE_REST = 0.25
#: What may close a line after its last word, and what ends a sentence: a line that ends in
#: one of these rests for a sentence.
_CLOSING = "\"')\N{RIGHT DOUBLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"
_FULL_STOPS = ".!?:\N{HORIZONTAL ELLIPSIS}"


def voice_source() -> str:
    return _VOICE_SOURCE.format(
        index=VOICE_INDEX,
        pace=QUIET_WORDS_A_SECOND,
        sentence=SENTENCE_REST,
        clause=CLAUSE_REST,
        closing=ascii(_CLOSING),
        stops=ascii(_FULL_STOPS),
    )


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


#: How an opening lists a film's chapters (ADR-079): up to this many to a column, and this
#: many columns to a screen; more, and the index turns to its next screen.
INDEX_ROWS = 10
INDEX_COLUMNS = 2
#: By how many columns the index has: the size its entries are set in, and how many
#: characters of a chapter's title an entry holds.
_INDEX_SET = {1: (30, 48), 2: (26, 34)}
#: The room between an entry's line and the next one's, in ems.
_INDEX_SPACING = 0.6
#: The room the index has below the course's name, wide and high. Every screen of it is set
#: at one size: the largest at which each one fits.
_INDEX_ROOM = (12.6, 5.6)


def _cut(text: str, width: int) -> str:
    """As much of a course's words as ``width`` characters hold, cut at a word, with an
    ellipsis where something was left off."""
    plain = " ".join(_NOT_SPOKEN.sub(" ", text).split())
    if len(plain) <= width:
        return plain
    room = plain[: width - 1]
    if plain[width - 1] != " " and " " in room:
        room = room.rsplit(" ", 1)[0]
    return room.rstrip(" ,;:-") + "\N{HORIZONTAL ELLIPSIS}"


def _entry(number: int, title: str, width: int) -> str:
    """A chapter as an entry of the opening's index: its number, and as much of its title as
    the column has room for."""
    entry = f"{number}. {_cut(title, width) or 'A chapter'}"
    return f"{number}. A chapter" if text_problem(entry) else entry


def opening_chapter(course: str, titles: Sequence[str]) -> PlainChapter:
    """What a film opens with (ADR-079): the course's name, and its chapters as an index, a
    screen of them at a time where there are many, every screen set at one size that fits.
    It is said in two lines, never chapter by chapter: what the film goes through and in
    how many chapters, and that here they are."""
    count = len(titles)
    many = "one chapter" if count == 1 else f"{count} chapters"
    # The course's name is made something a voice can say before it goes into the line, so
    # that what is taken out of it takes nothing of the line with it.
    first = f"This film goes through {spoken(course) or 'this course'}, in {many}."
    if spoken(first) != first:
        first = f"This film goes through this course, in {many}."
    second = "Here it is." if count == 1 else "Here they are, in order."
    heading = _cut(course, 40)
    if not heading or text_problem(heading):
        heading = "This course"
    body = [
        f"        title = m.Text({json.dumps(heading)}, font_size=44)",
        "        title.to_edge(m.UP, buff=0.5)",
        f"        self.say({json.dumps(first)}, m.Write(title))",
    ]
    size, width = _INDEX_SET[max(1, min(INDEX_COLUMNS, -(-count // INDEX_ROWS)))]
    per_screen = INDEX_ROWS * INDEX_COLUMNS
    pages: list[tuple[str, int]] = []
    for start in range(0, count, per_screen):
        screen = titles[start : start + per_screen]
        columns = []
        for top in range(0, len(screen), INDEX_ROWS):
            # A column is one paragraph, so that its entries stand on one grid of lines
            # whatever letters they hold.
            entries = ", ".join(
                json.dumps(_entry(start + top + row + 1, named, width))
                for row, named in enumerate(screen[top : top + INDEX_ROWS])
            )
            columns.append(
                f"m.Paragraph({entries}, font_size={size}, line_spacing={_INDEX_SPACING})"
            )
        page = f"page_{len(pages) + 1}"
        pages.append((page, len(screen)))
        body += [
            f"        {page} = m.VGroup({', '.join(columns)})",
            f"        {page}.arrange(m.RIGHT, aligned_edge=m.UP, buff=1.0)",
        ]
    if pages:
        wide, high = _INDEX_ROOM
        room = ", ".join(f"{wide} / {page}.width, {high} / {page}.height" for page, _ in pages)
        body.append(f"        fit = min(1, {room})")
        body += [f"        {page}.scale(fit).next_to(title, m.DOWN, buff=0.6)" for page, _ in pages]
    for at, (page, shown) in enumerate(pages):
        if at:
            body += [
                f"        self.play(m.FadeOut({pages[at - 1][0]}), run_time=0.5)",
                f"        self.play(m.FadeIn({page}), run_time=0.6)",
            ]
        else:
            body.append(f"        self.say({json.dumps(second)}, m.FadeIn({page}))")
        # Time to read the screen: a little for each chapter on it.
        body.append(f"        self.wait({round(min(8.0, max(2.0, 0.4 * shown)), 1)})")
    source = (
        '"""Adle\'s: the film\'s opening, and an index of its chapters."""\n'
        "import manimgx as m\n\n\n"
        f"class {CHAPTER_SCENE}(m.Scene):\n"
        "    def construct(self):\n" + "\n".join(body) + "\n"
    )
    return PlainChapter(source=source, lines=(first, second) if pages else (first,))


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
