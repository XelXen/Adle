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

from adle_core.generation.examples import EXAMPLES as SUBJECT_EXAMPLES
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
    # What an experiment is done in, in each of its shapes, and everything seen in one
    # (ADR-061): heat, a new color, more of it, bubbles, a solid, and each of them gone.
    "vessels": {
        "elements": [
            {"id": "a", "kind": "vessel", "shape": "test tube", "liquid": "blue", "level": 0.5, "label": "copper sulfate", "place": "left"},
            {"id": "b", "kind": "vessel", "shape": "flask", "liquid": "green", "level": 0.4, "label": "a flask", "place": "center"},
            {"id": "c", "kind": "vessel", "shape": "beaker", "level": 0.2, "label": "water", "place": "right"},
        ],
        "steps": [
            [{"show": ["a", "b", "c"]}],
            [{"set": "a", "to": "heat"}, {"color": "b", "to": "red"}, {"set": "c", "to": {"level": 0.8}}],
            [{"set": "a", "to": "bubbles"}, {"set": "b", "to": "precipitate"}, {"set": "c", "to": {"liquid": "purple", "bubbles": True}}],
            [{"set": "a", "to": "no heat"}, {"highlight": "b"}, {"set": "c", "to": "still"}],
            [{"hide": "a"}],
        ],
    },
    # Molecules: a chain, a branch, a ring with double bonds, two ions, a triple bond.
    "molecules": {
        "elements": [
            {"id": "water", "kind": "molecule", "atoms": ["H", "O", "H"], "bonds": [[1, 2], [2, 3]], "label": "water", "place": "top left"},
            {
                "id": "ethanol", "kind": "molecule", "label": "ethanol", "place": "top right",
                "atoms": ["C", "C", "O", "H", "H", "H", "H", "H", "H"],
                "bonds": [[1, 2], [2, 3], [1, 4], [1, 5], [1, 6], [2, 7], [2, 8], [3, 9]],
            },
            {
                "id": "ring", "kind": "molecule", "label": "a ring of carbon", "place": "bottom left",
                "atoms": ["C", "C", "C", "C", "C", "C"],
                "bonds": ["1=2", "2-3", "3=4", "4-5", "5=6", "6-1"],
            },
            {"id": "salt", "kind": "molecule", "atoms": ["Na+", "Cl-"], "label": "sodium chloride", "place": "bottom"},
            {"id": "nitrogen", "kind": "molecule", "atoms": ["N", "N"], "bonds": [[1, 2, 3]], "place": "bottom right"},
        ],
        "steps": [
            [{"show": ["water", "ethanol", "ring", "salt", "nitrogen"]}],
            [{"highlight": "water.2"}, {"color": "ethanol.3", "to": "yellow"}, {"highlight": "ring.b1"}],
        ],
    },
    # A timeline as full as one gets, its events coming one and two at a time.
    "timeline": {
        "elements": [
            {
                "id": "press", "kind": "timeline", "label": "The printing press", "place": "center",
                "events": [
                    {"at": "c. 1440", "text": "Gutenberg builds a press with movable type"},
                    {"at": "1455", "text": "The Gutenberg Bible is printed"},
                    {"at": "1470s", "text": "Presses in Italy, France and England"},
                    {"at": "1500", "text": "Millions of books in print"},
                    {"at": "1517", "text": "Luther's theses spread in print"},
                    {"at": "1600", "text": "Newspapers begin"},
                ],
            },
        ],
        "steps": [
            [{"show": "press.1"}],
            [{"show": ["press.2", "press.3"]}],
            [{"show": "press"}],
            [{"highlight": "press.5"}, {"color": "press.1455", "to": "yellow"}],
        ],
    },
    # Code: its lines one at a time, a line pointed at and one colored; and code written
    # as one text with a tab in it, and every mark a line of code may hold.
    "code": {
        "elements": [
            {
                "id": "c", "kind": "code", "label": "JavaScript", "place": "left",
                "lines": [
                    "function total(items) {", "  let sum = 0;", "  for (const item of items) {",
                    "    sum += item.price * item.count;", "  }", "  return sum;", "}",
                ],
            },
            {"id": "note", "kind": "text", "text": "One pass over the list.", "place": "right"},
            {
                "id": "py", "kind": "code", "place": "bottom right",
                "code": "if x < 10 and name != 'ada':\n\tprint(f\"{x:>4} % 3 = {x % 3}\")",
            },
        ],
        "steps": [
            [{"show": "c.1"}],
            [{"show": ["c.2", "c.3"]}],
            [{"show": "c"}, {"highlight": "c.4"}],
            [{"color": "c.line 6", "to": "green"}, {"show": ["note", "py"]}],
        ],
    },
    # What six real lessons asked of a slide (2026-11-24, ADR-061). A push drawn as an
    # arrow out of a cart, its words changed; two carts on one side of the same thing; a
    # quantity with its unit.
    "forces": {
        "elements": [
            {"id": "law", "kind": "math", "place": "center", "tex": "a = F / m"},
            {"id": "light", "kind": "shape", "shape": "rectangle", "label": "1 kg", "color": "blue", "place": {"left of": "law", "y": 2}},
            {"id": "heavy", "kind": "shape", "shape": "rectangle", "label": "4 kg", "color": "red", "place": {"left of": "law", "y": -2}},
            {"id": "push", "kind": "arrow", "from": "light", "to": {"right of": "light"}, "label": "10 N", "color": "green"},
            {"id": "pull", "kind": "arrow", "from": "heavy", "toward": "left", "label": "2.5 N", "color": "orange"},
            {"id": "weight", "kind": "arrow", "from": "heavy", "direction": "down", "color": "gray"},
            {"id": "lift", "kind": "line", "from": "light", "toward": "above", "color": "gray"},
            {"id": "note", "kind": "text", "text": "one rule", "place": {"right of": "law"}},
            {"id": "more", "kind": "text", "text": "for every cart", "place": {"right of": "law"}},
        ],
        "steps": [
            [{"show": ["light", "heavy", "push", "pull", "weight", "lift"]}],
            [{"show": ["law", "note", "more"]}],
            [{"set": "push", "to": {"label": "20 N"}}, {"set": "pull", "to": "5 N"}],
        ],
    },
    # A list sorted by hand: its cells set all at once and one at a time, an empty cell
    # filled, and the arrow that compares two of them moved along.
    "list_sorted": {
        "elements": [
            {"id": "list", "kind": "grid", "rows": [["5", "1", "4", ""]], "col_labels": ["0", "1", "2", "3"], "label": "list", "place": "center"},
            {"id": "compare", "kind": "arrow", "from": "list.1.1", "to": "list.1.2", "label": "compare", "color": "blue", "curved": True},
        ],
        "steps": [
            [{"show": "list"}],
            [{"show": "compare"}],
            [{"set": "list", "to": {"rows": [["1", "5", "4", ""]]}}, {"move": "compare", "to": {"from": "list.1.2", "to": "list.1.3"}}],
            [{"set": "list", "to": [["1", "4", "5", ""]]}, {"set": "list.1.4", "to": 8}],
            [{"set": "compare", "to": {"label": "sorted"}}, {"hide": "compare"}],
        ],
    },
    # Causes that all lead to one thing: the edges go round the nodes between their ends,
    # over a row and beside a column.
    "causes": {
        "elements": [
            {
                "id": "why", "kind": "nodes", "layout": "row", "place": "top", "color": "green",
                "nodes": ["debt", "hunger", "anger", "revolt"],
                "edges": [["debt", "revolt"], ["hunger", "revolt"], ["anger", "revolt"]],
            },
            {
                "id": "steps", "kind": "nodes", "layout": "column", "place": "bottom", "directed": False,
                "nodes": ["first", "second", "third"], "edges": [[1, 3], [1, 2]],
            },
        ],
        "steps": [[{"show": "why"}], [{"show": "steps"}], [{"highlight": "why.debt->revolt"}]],
    },
    # One thing moved through the places of two that are never shown, as a real lesson
    # moved a molecule through a membrane.
    "passing": {
        "elements": [
            {"id": "wall", "kind": "shape", "shape": "rectangle", "label": "membrane", "color": "orange", "place": "center"},
            {"id": "outside", "kind": "molecule", "atoms": ["O", "O"], "bonds": [[1, 2, 2]], "place": "top"},
            {"id": "inside", "kind": "molecule", "atoms": ["O", "O"], "bonds": [[1, 2, 2]], "place": "bottom"},
        ],
        "steps": [
            [{"show": ["wall", "outside"]}],
            [{"move": "outside", "to": "inside"}],
            [{"highlight": "inside"}, {"color": "inside", "to": "yellow"}],
        ],
    },
    # A picture drawn again as a learner asked (ADR-067): a hydrogen bond, a dashed line from
    # an atom of one molecule to an atom of the next.
    "hydrogen_bond": {
        "elements": [
            {"id": "upper", "kind": "molecule", "atoms": ["O", "H", "H"], "bonds": [[1, 2], [1, 3]], "place": "top", "label": "water"},
            {"id": "lower", "kind": "molecule", "atoms": ["O", "H", "H"], "bonds": [[1, 2], [1, 3]], "place": "bottom", "label": "water"},
            {"id": "bond", "kind": "line", "from": "upper.2", "to": "lower.1", "dashed": True, "color": "teal", "label": "hydrogen bond"},
        ],
        "steps": [[{"show": ["upper", "lower"]}], [{"show": "bond"}]],
    },
    # Characters written small, a liquid with no color, and something put under what
    # stands at the foot of the stage: it goes above it instead.
    "small_marks": {
        "elements": [
            {"id": "jar", "kind": "vessel", "liquid": "colorless", "label": "H₂O", "place": "left"},
            {"id": "ions", "kind": "molecule", "atoms": ["Na⁺", "Cl⁻"], "label": "Na⁺ + Cl⁻ (aq)", "place": "right"},
            {"id": "unit", "kind": "text", "text": "x² + y² in m/s²", "place": "top"},
            {"id": "eq", "kind": "math", "tex": "\\mathrm{HCl} + \\mathrm{NaOH} \\rightarrow \\mathrm{NaCl} + \\mathrm{H_2O}", "place": "bottom"},
            {"id": "care", "kind": "text", "text": "In a laboratory, with goggles.", "place": {"below": "eq"}, "color": "red"},
        ],
        "steps": [
            [{"show": ["jar", "ions", "unit"]}],
            [{"color": "jar", "to": "pink"}, {"show": ["eq", "care"]}],
            [{"set": "jar", "to": {"liquid": "colorless"}}],
        ],
    },
}  # fmt: skip


#: The example part a lesson's writer is shown, one for each way a subject is taught
#: (``generation/examples.py``, ADR-061): each is drawn like the rest. The general one
#: keeps the name it had when it was the only one.
for _key, _example in SUBJECT_EXAMPLES.items():
    _name = "prompt_example" if _key == "area" else f"example_{_key}"
    EXAMPLES[_name] = _example.part["visual"]


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
