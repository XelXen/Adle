"""Which of the figures in real lesson answers Adle can draw, and why not the others.

A developer's tool. It reads answers a model wrote, as `real_provider_check.py` keeps them
(`<out>/NN-<provider>-lesson.answer.txt`), and asks the figure module to compile every
figure in them, offline: no request is made and nothing is written. It is how the shapes a
model means and the format did not take were found (ADR-045); run it on the answers of a
new model or a new prompt before trusting either.

    uv run --directory services/core python ../../scripts/dev/figure_census.py \\
        <answer file> [<answer file> ...]

For each answer: how many of its figures compile, and the reason for each that does not.
At the end: the figures drawn of all of them. The answers stay where they are: what a
model wrote from someone's documents does not belong in the repository.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from adle_core.generation.drafts import DraftError, extract_json_object
from adle_core.generation.figures import FigureError, compile_figure

#: Each figure is paced to four sentences said over it: enough to compile any kind.
BEATS = [6.0] * 4


def say(line: str) -> None:
    sys.stdout.write(f"{line}\n")


def census(path: Path) -> tuple[int, int, list[str]]:
    """How many figures the answer in ``path`` has, how many compile, and why the rest not."""
    data = extract_json_object(path.read_text(encoding="utf-8"))
    segments = data.get("segments") if isinstance(data, dict) else None
    figures = [
        segment["figure"]
        for segment in (segments if isinstance(segments, list) else [])
        if isinstance(segment, dict) and segment.get("figure")
    ]
    drawn, problems = 0, []
    for figure in figures:
        try:
            compile_figure(figure, beat_seconds=BEATS)
            drawn += 1
        except FigureError as error:
            kind = figure.get("kind") if isinstance(figure, dict) else type(figure).__name__
            problems.append(f"{kind}: {error}")
    return len(figures), drawn, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("answers", nargs="+", type=Path)
    args = parser.parse_args()
    total = drawn = 0
    for path in args.answers:
        try:
            count, made, problems = census(path)
        except (OSError, DraftError) as error:
            say(f"{path}: not read ({type(error).__name__})")
            continue
        total += count
        drawn += made
        say(f"{path.parent.name}/{path.name}: {made} of {count}")
        for problem in problems:
            say(f"  {problem}")
    say(f"drawn: {drawn} of {total}")
    return 0 if drawn == total else 1


if __name__ == "__main__":
    sys.exit(main())
