"""Write one scene of every kind of figure, as the core draws them, for the player to run
(ADR-045). The end-to-end suite runs each to completion in both themes
(``apps/desktop/e2e/scene-player.spec.ts``); ``tests/unit/test_figures.py`` fails if these files
are not what the figures module writes now.

    npm run figures
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from adle_core.generation.figures import compile_figure

#: Beats of an ordinary part of a lesson: three sentences of about a dozen words.
BEATS = [4.8, 5.2, 4.4]

#: An example of each kind, with every optional part of it used somewhere.
EXAMPLES: dict[str, dict[str, Any]] = {
    "equation": {
        "kind": "equation",
        "steps": [
            r"E[X] = \int_0^1 x \cdot 2x \, dx",
            r"E[X] = \int_0^1 2x^2 \, dx",
            r"E[X] = \dfrac{2}{3}",
        ],
    },
    "graph": {
        "kind": "graph",
        "x": [0, 4],
        "x_label": "x",
        "y_label": "f(x)",
        "curves": [{"f": "exp(-x)", "label": r"f(x) = e^{-x}"}],
        "shade": {"curve": 1, "from": 0.5, "to": 2, "label": r"P(0.5 \le X \le 2)"},
        "points": [{"x": 1, "label": "x = 1"}],
        "trace": True,
    },
    "graph_two_curves": {
        "kind": "graph",
        "x": [-3, 3],
        "curves": [
            {"f": "x^2", "label": "x^2"},
            {"f": "2x", "label": "2x", "from": -1.5, "to": 3},
        ],
    },
    "graph_slider": {
        "kind": "graph",
        "x": [-4, 4],
        "x_label": "x",
        "curves": [{"f": "exp(-(x - mu)^2 / 2) / sqrt(2 pi)", "label": "f(x)"}],
        "shade": {"from": -1, "to": 1},
        "slider": {"name": "mu", "label": r"\mu", "min": -2, "max": 2, "value": 0},
    },
    "graph_area_follows": {
        "kind": "graph",
        "x": [-1, 5],
        "x_label": "x",
        "curves": [{"f": "(x >= 0) * exp(-x)", "label": "f(x)"}],
        "shade": {"from": 0, "to": "a", "label": "F(a)"},
        "slider": {"name": "a", "label": "a", "min": 0, "max": 4, "value": 1},
    },
    "graph_rise": {
        "kind": "graph",
        "x": [-1, 11],
        "x_label": "x",
        "y_label": "F(x)",
        "curves": [{"f": "(x >= 0 && x <= 10) * x / 10 + (x > 10) * 1", "label": "F(x)"}],
        "rise": [
            {"from": 0, "to": 2, "label": r"P(X \le 2)"},
            {"from": 5, "to": 8, "label": r"P(5 < X \le 8)"},
        ],
    },
    "graph_functions": {
        "kind": "graph",
        "x": [-3, 3],
        "x_label": "x",
        "curves": [
            {"f": "tanh(x)", "label": r"\tanh x"},
            {"f": "0.5 * (1 + erf(x / sqrt(2)))", "label": r"\Phi(x)"},
        ],
    },
    "bars": {
        "kind": "bars",
        "labels": ["0", "1", "2"],
        "values": [0.25, 0.5, 0.25],
        "then": [0.1, 0.6, 0.3],
        "highlight": 2,
        "y_label": "P(X = x)",
    },
    "number_line": {
        "kind": "number_line",
        "from": -3,
        "to": 3,
        "marks": [{"at": -1.96, "label": "-1.96"}, {"at": 1.96, "label": "1.96"}],
        "interval": {"from": -1.96, "to": 1.96, "label": r"95\%"},
        "move": {"from": 0, "to": 1.5},
    },
    "flow": {
        "kind": "flow",
        "steps": ["Collect the data", "Fit the model", "Check the fit"],
        "loop": True,
    },
    "flow_two_rows": {
        "kind": "flow",
        "steps": ["Read", "Plan", "Write", "Check", "Revise"],
    },
    "layers": {
        "kind": "layers",
        "layers": [
            {"label": "inputs", "nodes": 3},
            {"label": "hidden", "nodes": 4},
            {"label": "output", "nodes": 1},
        ],
        "path": [1, 2, 1],
    },
    "table": {
        "kind": "table",
        "header": ["x", "$f(x)$", "$F(x)$"],
        "rows": [["0", "0", "0"], ["0.5", "1", "0.25"], ["1", "2", "1"]],
        "highlight": [2],
    },
    "table_words": {
        "kind": "table",
        "header": ["Property", "In symbols"],
        "rows": [
            ["Starts at zero", r"$F(-\infty) = 0$"],
            ["Never falls", r"If $a < b$ then $F(a) \le F(b)$"],
            ["Ends at one", r"$F(\infty) = 1$"],
        ],
        "highlight": [2],
    },
    "scatter": {
        "kind": "scatter",
        "points": [[1, 2.1], [2, 3.9], [3, 6.2], [4, 7.8], [5, 10.1]],
        "line": {"slope": 2, "intercept": 0, "label": r"\hat y = 2x"},
        "residuals": True,
        "x_label": "x",
        "y_label": "y",
    },
    "vectors": {
        "kind": "vectors",
        "vectors": [{"x": 2, "y": 1, "label": r"\vec a"}, {"x": 1, "y": 2, "label": r"\vec b"}],
        "sum": True,
    },
    "tree": {
        "kind": "tree",
        "nodes": [
            {"label": "Start"},
            {"label": "H", "parent": 1, "edge": r"\tfrac{1}{2}"},
            {"label": "T", "parent": 1, "edge": r"\tfrac{1}{2}"},
            {"label": "HH", "parent": 2, "edge": r"\tfrac{1}{2}"},
            {"label": "HT", "parent": 2, "edge": r"\tfrac{1}{2}"},
        ],
    },
}


def written() -> dict[str, str]:
    """Each example's file name and the scene the figures module writes for it."""
    return {
        f"{name}.py": compile_figure(example, beat_seconds=BEATS).source
        for name, example in EXAMPLES.items()
    }


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m adle_core.tools.export_figures <folder>")
        return 2
    folder = Path(argv[0])
    folder.mkdir(parents=True, exist_ok=True)
    files = written()
    for stale in folder.glob("*.py"):
        if stale.name not in files:
            stale.unlink()
    for name, source in files.items():
        (folder / name).write_text(source, encoding="utf-8", newline="\n")
    print(f"wrote {len(files)} figures to {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
