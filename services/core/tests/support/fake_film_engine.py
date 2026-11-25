"""A stand-in for the film engine, ManimGX (ADR-065), for tests: the same command line and
the same report, and nothing drawn.

``inspect <file> <scene>`` and ``render <file> <scene> -o <video> ...`` read the scene file
Adle wrote (one chapter with its voice, or the whole film), find the chapters it plays, and
time each of their lines: by the recording the film's voice index names, or at 2.6 words a
second for a line nobody recorded. A play or a wait is a second unless it says otherwise.
``render`` writes a small real video (``film.mp4`` beside this file) where it was asked to,
and the subtitles beside it. As ManimGX does, it keeps what was said for a line in ``voice/``
beside the scene, named by the line alone (the engine names it by the voice's code too,
which is the same whatever has been recorded), and says it from there the next time.

A chapter can ask for trouble with a comment, to test what Adle does about it:

* ``# fake: overlap``: words over words, at that line;
* ``# fake: stop``: the scene stops there with an error;
* ``# fake: stop when joined``: the same, but only once it is part of the whole film;
* ``# fake: hang``: the scene never ends;
* ``# fake: cold``: the first run with an engine home never ends, as the real engine's first
  run is slow while the graphics driver compiles its shaders into that home; the next is as
  quick as ever;
* ``# fake: no storyboard``: ``inspect`` draws no storyboard.

``inspect`` draws a storyboard as ManimGX does, beside the scene: a sheet for every six
plays, ``<Scene>.storyboard.png`` and then ``<Scene>.storyboard-2.png`` and on, each a small
gray PNG (ADR-066).

The engine runs with none of the test's environment (``film.runtime.bare_environment``), so
everything it is told is in the files of the folder it runs in.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIDEO = HERE / "film.mp4"
WORDS_A_SECOND = 2.6
_CHAPTER = re.compile(r"^import (chapter_\d\d)\s*$", re.MULTILINE)
_MARK = re.compile(r"#\s*fake:\s*(overlap|stop when joined|stop|hang|cold|no storyboard)\s*$")
#: One sheet of a storyboard: a PNG of four by three gray pixels.
SHEET = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAADCAAAAACRn/EaAAAADklEQVR4nGNwAAIGOAEAFo8DAQJfVrUAAAAASUVORK5CYII="
)


def _number(node: ast.AST | None, default: float) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    return default


def _said(text: str) -> str:
    return " ".join(text.replace("[", "").replace("]", "").split())


def _plays(
    folder: Path, module: str, recorded: dict[str, object]
) -> list[tuple[int, float, str, str]]:
    """Each play of a chapter, in the order of its lines: its line, how long it is, what it
    is, and what it says."""
    tree = ast.parse((folder / f"{module}.py").read_text(encoding="utf-8"))
    found: list[tuple[int, float, str, str]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr in ("say", "play", "wait")
        ):
            continue
        if node.func.attr == "say":
            first = node.args[0] if node.args else None
            text = first.value if isinstance(first, ast.Constant) else ""
            said = _said(str(text))
            kept = folder / "voice" / f"{hashlib.sha256(said.encode()).hexdigest()[:16]}.json"
            known = recorded.get(said)
            if kept.is_file():
                seconds = float(json.loads(kept.read_text(encoding="utf-8"))["seconds"])
            elif isinstance(known, dict) and known.get("words"):
                seconds = max(0.5, float(known["words"][-1][2]))
            else:
                seconds = max(1.2, len(said.split()) / WORDS_A_SECOND)
            kept.parent.mkdir(exist_ok=True)
            kept.write_text(json.dumps({"seconds": seconds}), encoding="utf-8")
            found.append((node.lineno, seconds, f"say {said[:28]!r}", said))
        elif node.func.attr == "wait":
            seconds = _number(node.args[0] if node.args else None, 1.0)
            found.append((node.lineno, seconds, "wait", ""))
        else:
            run_time = next(
                (keyword.value for keyword in node.keywords if keyword.arg == "run_time"), None
            )
            found.append((node.lineno, _number(run_time, 1.0), "play", ""))
    return sorted(found)


def _marks(folder: Path, module: str) -> list[tuple[int, str]]:
    lines = (folder / f"{module}.py").read_text(encoding="utf-8").splitlines()
    marks: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        found = _MARK.search(line)
        if found:
            marks.append((number, found.group(1)))
    return marks


def main(arguments: list[str]) -> int:
    command, file, scene = arguments[0], arguments[1], arguments[2]
    folder = Path.cwd()
    try:
        recorded = json.loads((folder / "voice.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        recorded = {}
    whole = file == "film.py"
    modules = _CHAPTER.findall((folder / file).read_text(encoding="utf-8"))
    clock = 0.0
    plays: list[str] = []
    problems: list[str] = []
    drawn = True
    cues: list[tuple[float, float, str]] = []
    for module in modules:
        for line, kind in _marks(folder, module):
            if kind == "hang":
                time.sleep(3600)
            if kind == "cold":
                warm = Path(os.environ["HOME"]) / "warm"
                if not warm.exists():
                    warm.write_text("compiled", encoding="utf-8")
                    time.sleep(3600)
            if kind == "stop" or (kind == "stop when joined" and whole):
                print(f"{module}.py:{line}: in construct", file=sys.stderr)
                print("    self.play(...)", file=sys.stderr)
                print("ValueError: the scene stopped on purpose", file=sys.stderr)
                return 1
            if kind == "no storyboard":
                drawn = False
            if kind == "overlap":
                problems.append(
                    f"  [{len(problems) + 1}] t={clock:.2f}–{clock + 1:.2f}s ({module}.py:{line})  "
                    "label (Text 'side'): overlaps title (Text 'A title')"
                )
        for line, seconds, what, said in _plays(folder, module, recorded):
            plays.append(
                f"  #{len(plays):<3} {clock:5.2f}–{clock + seconds:5.2f}s  {module}.py:{line}  {what}"
            )
            if said:
                cues.append((clock, clock + seconds, said))
            clock += seconds
        if whole:
            clock += 1.0
    if command == "render":
        video = Path(arguments[arguments.index("-o") + 1])
        shutil.copyfile(VIDEO, video)
        with video.with_suffix(".srt").open("w", encoding="utf-8") as subtitles:
            for number, (start, end, text) in enumerate(cues, start=1):
                subtitles.write(f"{number}\n{_stamp(start)} --> {_stamp(end)}\n{text}\n\n")
        print(f"{video.name}  {clock:.2f} s, 1920x1080 at 30 fps, 0.0 MB (rendered in 0.1 s)")
    else:
        print(f"{file}: {scene}, {clock:.2f} s, {len(plays)} plays")
        if drawn:
            names = [
                f"{scene}.storyboard{'' if number == 1 else f'-{number}'}.png"
                for number in range(1, max(1, (len(plays) + 5) // 6) + 1)
            ]
            for name in names:
                (folder / name).write_bytes(SHEET)
            print(f"storyboard: {', '.join(names)}")
        for play in plays:
            print(play)
    if problems:
        print(f"layout: {len(problems)} problems")
        for problem in problems:
            print(problem)
        return 1
    print(f"layout: no problems in {len(plays)} samples")
    return 0


def _stamp(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600:02d}:{whole // 60 % 60:02d}:{whole % 60:02d},{int(seconds * 1000) % 1000:03d}"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
