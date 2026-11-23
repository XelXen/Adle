"""Write one slide of every kind of element, as the core draws them, for the player to run
(ADR-049). The end-to-end suite steps through each in both themes
(``apps/desktop/e2e/slide-player.spec.ts``); ``tests/unit/test_slides.py`` fails if these files
are not what the slides module writes now.

    npm run slides
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from adle_core.generation.prompts import visual_example
from adle_core.generation.slides import compile_slide

#: An example of each kind of element and of each verb, as a model would write them.
EXAMPLES: dict[str, dict[str, Any]] = {
    "sample_space": {
        "elements": [
            {"id": "coin", "kind": "coin", "face": "H", "place": "left", "label": "one flip"},
            {
                "id": "omega", "kind": "set", "items": ["H", "T"], "label": "\\Omega",
                "place": "center", "color": "blue",
            },
            {"id": "event", "kind": "outline", "around": "omega.H", "label": "E", "color": "yellow"},
            {
                "id": "rule", "kind": "math", "place": "right",
                "tex": "P(E) = \\frac{\\color{yellow}{1}}{\\color{blue}{2}}",
            },
        ],
        "steps": [
            [{"show": "coin"}],
            [{"set": "coin", "to": "T"}, {"show": "omega"}],
            [{"highlight": "omega.H"}],
            [{"show": "event"}, {"color": "omega.H", "to": "yellow"}],
            [{"show": "rule"}],
        ],
    },
    "dice_grid": {
        "elements": [
            {
                "id": "sums", "kind": "grid", "place": "left", "label": "first die by second die",
                "rows": [[str(a + b) for b in range(1, 7)] for a in range(1, 7)],
                "row_labels": [str(a) for a in range(1, 7)],
                "col_labels": [str(b) for b in range(1, 7)],
            },
            {
                "id": "rule", "kind": "math", "place": "right",
                "tex": "P(\\text{sum} = 7) = \\frac{\\color{yellow}{6}}{36} = \\frac{1}{6}",
            },
        ],
        "steps": [
            [{"show": "sums"}],
            [{"color": [f"sums.{a}.{7 - a}" for a in range(1, 7)], "to": "yellow"}],
            [{"show": "rule"}],
            [{"highlight": "rule"}],
        ],
    },
    "tangent": {
        "elements": [
            {"id": "a", "kind": "param", "value": 1, "min": 0, "max": 3, "slider": True, "label": "a"},
            {
                "id": "plane", "kind": "axes", "x": [-1, 4], "x_label": "x", "y_label": "y",
                "place": "left",
            },
            {"id": "f", "kind": "curve", "on": "plane", "f": "x^2 / 2", "label": "f(x)", "color": "blue"},
            {"id": "P", "kind": "point", "on": "f", "x": "a", "label": "P"},
            {"id": "touch", "kind": "tangent", "at": "P", "color": "yellow"},
            {"id": "slope", "kind": "number", "value": "a", "label": "slope", "place": "right"},
            {
                "id": "why", "kind": "text", "place": {"below": "slope"},
                "text": "The slope of the tangent at a is a itself.",
            },
        ],
        "steps": [
            [{"show": ["plane", "f"]}],
            [{"show": "P"}],
            [{"show": ["touch", "slope"]}],
            [{"set": "a", "to": 2.5}],
            [{"set": "a", "to": 0.5}, {"show": "why"}],
        ],
    },
    "area": {
        "elements": [
            {"id": "b", "kind": "param", "value": 1, "min": 0.2, "max": 4, "slider": True, "label": "b"},
            {"id": "plane", "kind": "axes", "x": [0, 4], "x_label": "x", "place": "top"},
            {"id": "f", "kind": "curve", "on": "plane", "f": "exp(-x)", "color": "blue"},
            {"id": "under", "kind": "area", "under": "f", "from": 0, "to": "b", "color": "yellow"},
            {
                "id": "total", "kind": "math", "place": "bottom",
                "tex": "{{\\int_0^b e^{-x}\\,dx}} = {{1 - e^{-b}}}",
            },
        ],
        "steps": [
            [{"show": "f"}],
            [{"show": "under"}],
            [{"set": "b", "to": 3}],
            [{"show": "total"}, {"color": "total.1", "to": "yellow"}],
        ],
    },
    "parts_of_speech": {
        "elements": [
            {
                "id": "s", "kind": "words", "place": "center", "size": "large",
                "text": "The quick brown fox jumps over the lazy dog.",
            },
            {"id": "noun", "kind": "label", "on": "s.fox", "text": "noun", "side": "below", "color": "blue"},
            {
                "id": "adjectives", "kind": "label", "on": "s.quick brown", "text": "adjectives",
                "side": "below", "color": "green",
            },
            {"id": "verb", "kind": "label", "on": "s.jumps", "text": "verb", "side": "above", "color": "coral"},
            {"id": "describes", "kind": "arrow", "from": "s.quick brown", "to": "s.fox", "color": "green"},
        ],
        "steps": [
            [{"show": "s"}],
            [{"color": "s.fox", "to": "blue"}, {"show": "noun"}],
            [{"color": "s.quick brown", "to": "green"}, {"show": "adjectives"}],
            [{"color": "s.jumps", "to": "red"}, {"show": "verb"}],
            [{"show": "describes"}],
        ],
    },
    "passive_voice": {
        "elements": [
            {"id": "active", "kind": "words", "text": "The cat chased the mouse", "place": "top"},
            {"id": "passive", "kind": "words", "text": "The mouse was chased by the cat", "place": "top"},
            {"id": "note", "kind": "box", "text": "The object moves to the front.", "place": "bottom", "color": "violet"},
        ],
        "steps": [
            [{"show": "active"}],
            [{"highlight": ["active.mouse", "active.cat"]}],
            [{"transform": "active", "into": "passive"}],
            [{"show": "note"}],
        ],
    },
    "linked_list": {
        "elements": [
            {
                "id": "list", "kind": "nodes", "place": "center", "color": "teal",
                "nodes": ["head", "3", "7", "9", "null"],
                "edges": [["head", "3"], ["3", "7"], ["7", "9"], ["9", "null"]],
            },
            {"id": "note", "kind": "text", "text": "Each node points to the next one.", "place": "bottom"},
        ],
        "steps": [
            [{"show": ["list.head", "list.3"]}],
            [{"show": ["list.7", "list.head->3", "list.3->7"]}],
            [{"show": "list"}, {"highlight": "list.9"}],
            [{"show": "note"}],
        ],
    },
    "tree": {
        "elements": [
            {
                "id": "calls", "kind": "nodes", "layout": "tree", "place": "center",
                "nodes": ["fib(3)", "fib(2)", "fib(1)", "fib(1)", "fib(0)"],
                "edges": [[1, 2], [1, 3], [2, 4], [2, 5]],
            },
        ],
        "steps": [[{"show": "calls"}], [{"color": "calls.2", "to": "yellow"}]],
    },
    "rolls": {
        "elements": [
            {
                "id": "counts", "kind": "bars", "place": "center", "label": "rolls of a die",
                "labels": ["1", "2", "3", "4", "5", "6"], "values": [1, 1, 1, 1, 1, 1],
            },
        ],
        "steps": [
            [{"show": "counts"}],
            [{"set": "counts", "to": [8, 12, 9, 11, 10, 10]}],
            [{"highlight": "counts.2"}],
        ],
    },
    "number_line": {
        "elements": [
            {"id": "line", "kind": "number_line", "x": [0, 10], "label": "x", "place": "center"},
            {"id": "X", "kind": "point", "on": "line", "x": 2, "label": "X", "color": "coral"},
            {"id": "where", "kind": "text", "text": "X lands somewhere between 0 and 10.", "place": "top"},
        ],
        "steps": [[{"show": ["line", "where"]}], [{"show": "X"}], [{"set": "X", "to": 7}]],
    },
    "vectors": {
        "elements": [
            {"id": "plane", "kind": "axes", "x": [-1, 5], "y": [-1, 4], "place": "center"},
            {"id": "u", "kind": "vector", "on": "plane", "to": [3, 1], "label": "u", "color": "blue"},
            {"id": "v", "kind": "vector", "on": "plane", "from": [3, 1], "to": [4, 3], "label": "v", "color": "green"},
            {"id": "w", "kind": "vector", "on": "plane", "to": [4, 3], "label": "u + v", "color": "yellow"},
        ],
        "steps": [[{"show": ["plane", "u"]}], [{"show": "v"}], [{"show": "w"}]],
    },
    "solve": {
        "elements": [
            {"id": "eq", "kind": "math", "tex": "2x + 3 = 11", "place": "center", "size": "large"},
            {"id": "how", "kind": "text", "text": "Undo each step, on both sides.", "place": "bottom"},
        ],
        "steps": [
            [{"show": "eq"}],
            [{"set": "eq", "to": "2x = 8"}, {"show": "how"}],
            [{"set": "eq", "to": "x = 4"}],
            [{"highlight": "eq"}, {"hide": "how"}],
        ],
    },
    "table": {
        "elements": [
            {
                "id": "law", "kind": "table", "place": "left",
                "header": ["$x$", "$P(X = x)$"],
                "rows": [["0", "\\frac{1}{4}"], ["1", "\\frac{1}{2}"], ["2", "\\frac{1}{4}"]],
            },
            {"id": "flips", "kind": "text", "text": "Heads in two flips of a coin", "place": "right"},
        ],
        "steps": [
            [{"show": ["law", "flips"]}],
            [{"highlight": "law.row 2"}],
            [{"color": "law.2.2", "to": "yellow"}],
        ],
    },
    "dice_and_count": {
        "elements": [
            {"id": "die", "kind": "die", "face": 1, "place": "left", "label": "roll"},
            {"id": "sixes", "kind": "number", "value": 0, "decimals": 0, "label": "sixes", "place": "right"},
        ],
        "steps": [
            [{"show": ["die", "sixes"]}],
            [{"set": "die", "to": 4}],
            [{"set": "die", "to": 6}, {"set": "sixes", "to": 1}],
        ],
    },
    "distance": {
        "elements": [
            {"id": "A", "kind": "dot", "label": "A", "place": "left", "color": "blue"},
            {"id": "B", "kind": "dot", "label": "B", "place": "right", "color": "green"},
            {"id": "gap", "kind": "line", "from": "A", "to": "B", "dashed": True, "label": "d"},
            {"id": "rule", "kind": "math", "tex": "d = |B - A|", "place": "bottom"},
        ],
        "steps": [[{"show": ["A", "B"]}], [{"show": "gap"}], [{"show": "rule"}]],
    },
    "machine": {
        "elements": [
            {"id": "input", "kind": "shape", "shape": "rectangle", "label": "x = 3", "place": "left", "color": "blue"},
            {"id": "rule", "kind": "shape", "shape": "circle", "label": "f", "place": "center", "color": "violet"},
            {"id": "output", "kind": "shape", "shape": "rectangle", "label": "f(3) = 9", "place": "right", "color": "green"},
            {"id": "in", "kind": "arrow", "from": "input", "to": "rule"},
            {"id": "out", "kind": "arrow", "from": "rule", "to": "output", "label": "square it"},
            {"id": "count", "kind": "brace", "over": ["input", "output"], "label": "one output for each input"},
        ],
        "steps": [
            [{"show": ["input", "rule"]}],
            [{"show": "in"}],
            [{"show": ["out", "output"]}],
            [{"show": "count"}],
            [{"move": "output", "to": {"below": "rule"}}],
        ],
    },
    # A count made of the picture (ADR-050): the event's mark and the whole set fly into the
    # numbers of the case, which then become the rule's symbols.
    "counted_out": {
        "elements": [
            {
                "id": "omega", "kind": "set", "items": ["HH", "HT", "TH", "TT"], "label": "\\Omega",
                "place": "left", "color": "blue",
            },
            {"id": "event", "kind": "outline", "around": ["omega.HH", "omega.HT"], "label": "E", "color": "yellow"},
            {
                "id": "count", "kind": "math", "place": "right",
                "tex": "P(E) = {{\\color{yellow}{2}}} / {{\\color{blue}{4}}}",
            },
            {
                "id": "rule", "kind": "math", "place": "right",
                "tex": "P(E) = {{\\color{yellow}{|E|}}} / {{\\color{blue}{|\\Omega|}}}",
            },
        ],
        "steps": [
            [{"show": "omega"}],
            [{"color": ["omega.HH", "omega.HT"], "to": "yellow"}, {"show": "event"}],
            [{"show": "count", "from": ["event", "omega"]}],
            [{"transform": "count", "into": "rule"}],
        ],
    },
    # A sentence or an equation made of the one before it (ADR-050): what they share moves.
    "rewritten": {
        "elements": [
            {"id": "active", "kind": "words", "place": "top", "text": "The dog chased the ball.", "color": "blue"},
            {"id": "passive", "kind": "words", "place": {"below": "active"}, "text": "The ball was chased by the dog.", "color": "green"},
            {"id": "first", "kind": "math", "place": "bottom", "tex": "2x + 3 = 7"},
            {"id": "next", "kind": "math", "place": {"below": "first"}, "tex": "2x = 4"},
        ],
        "steps": [
            [{"show": "active"}],
            [{"show": "passive"}],
            [{"show": "first"}],
            [{"show": "next"}],
        ],
    },
    # As a real model wrote them (2026-11-22): tangents at points written inline, a line to
    # one, and labels on the tangents.
    "tangents_inline": {
        "elements": [
            {"id": "axes", "kind": "axes", "place": "center", "x": [-3, 3], "y": [-1, 5], "x_label": "x", "y_label": "y"},
            {"id": "curve", "kind": "curve", "on": "axes", "f": "x^2", "from": -3, "to": 3, "color": "blue"},
            {"id": "left", "kind": "tangent", "at": {"x": -2, "on": "curve"}, "color": "red"},
            {"id": "flat", "kind": "tangent", "at": 0, "color": "green"},
            {"id": "negative", "kind": "label", "on": "left", "text": "f' < 0", "side": "left", "color": "red"},
            {"id": "zero", "kind": "label", "on": "flat", "text": "f' = 0", "side": "above", "color": "green"},
            {"id": "secant", "kind": "line", "from": {"x": 1, "on": "curve"}, "to": {"x": 2, "on": "curve"}, "dashed": True},
        ],
        "steps": [
            [{"show": ["axes", "curve"]}],
            [{"show": ["left", "negative"]}],
            [{"show": ["flat", "zero"]}],
            [{"show": "secant"}],
        ],
    },
    # As a real model wrote it: a point moved by {"x": ...}, numbers that follow it, and a
    # slider nothing followed, which moves the point.
    "point_readouts": {
        "elements": [
            {"id": "axes", "kind": "axes", "place": "left", "x": [-3, 3], "y": [-1, 9]},
            {"id": "curve", "kind": "curve", "on": "axes", "f": "x^2", "color": "blue"},
            {"id": "p", "kind": "point", "on": "curve", "x": -2, "color": "red"},
            {"id": "tangent", "kind": "tangent", "at": "p", "color": "violet"},
            {"id": "where", "kind": "number", "place": "top right", "value": "p.x", "decimals": 1, "label": "x", "color": "red"},
            {"id": "slope", "kind": "number", "place": {"below": "where"}, "value": "2*p.x", "decimals": 1, "label": "f'(x)", "color": "violet"},
            {"id": "x_value", "kind": "param", "value": -2, "min": -3, "max": 3, "slider": True},
        ],
        "steps": [
            [{"show": ["axes", "curve", "p", "tangent", "where", "slope"]}],
            [{"set": "p", "to": {"x": 0}}, {"set": "x_value", "to": 0}],
            [{"set": "p", "to": {"x": 2}}, {"set": "x_value", "to": 2}],
        ],
    },
    # A formula shown at once beside its case waits for the next step (ADR-050).
    "case_first": {
        "elements": [
            {"id": "die", "kind": "die", "face": 3, "place": "left", "label": "one roll"},
            {"id": "odds", "kind": "math", "place": "right", "tex": "P(\\text{odd}) = \\frac{3}{6}"},
        ],
        "steps": [[{"show": ["die", "odds"]}], [{"set": "die", "to": 5}]],
    },
}  # fmt: skip


#: The example the lesson prompt itself shows a model: it is drawn like the rest.
EXAMPLES["prompt_example"] = visual_example()["visual"]


def written() -> dict[str, str]:
    """Each example's file name and the scene the slides module writes for it."""
    return {f"{name}.py": compile_slide(example).source for name, example in EXAMPLES.items()}


def steps() -> dict[str, dict[str, Any]]:
    """How many steps each example takes, and whether it ends on a live page."""
    found = {}
    for name, example in EXAMPLES.items():
        slide = compile_slide(example)
        found[f"{name}.py"] = {"steps": slide.steps, "interactive": slide.interactive}
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: export_slides <folder>", file=sys.stderr)
        return 2
    folder = Path(argv[0])
    folder.mkdir(parents=True, exist_ok=True)
    files = written()
    for stale in folder.glob("*.py"):
        if stale.name not in files:
            stale.unlink()
    for name, source in files.items():
        (folder / name).write_text(source, encoding="utf-8", newline="\n")
    (folder / "steps.json").write_text(
        json.dumps(steps(), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {len(files)} slides to {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
