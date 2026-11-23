"""Figures: a lesson's pictures drawn by the core from tested templates (ADR-045).

What the model gives is data. Text goes into the scene as a literal; a graph's formula is
read by a parser that takes arithmetic and a few functions and nothing else, and is tried
before it is drawn; every scene written passes the scene policy. Whether each kind runs is
the player's to say: the end-to-end suite runs the files ``npm run figures`` writes, and the
last test here keeps those files what the module writes now.
"""

from __future__ import annotations

import ast
import copy
import math
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from adle_core.generation.figures import (
    FIGURE_KINDS,
    FigureError,
    _function,
    _paced,
    _python_expression,
    _tex_parts,
    compile_figure,
)
from adle_core.generation.scene_policy import check_scene_source
from adle_core.lessons.bundle import inspect_scene
from adle_core.lessons.ir import LongDisplay
from adle_core.tools.export_figures import BEATS, EXAMPLES, written

FIGURES = Path(__file__).resolve().parents[4] / "apps" / "desktop" / "e2e" / "fixtures" / "figures"


#: The examples a learner operates, and the control each has.
OPERATED = {"graph_slider": ["mu"], "graph_area_follows": ["a"]}


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_every_kind_is_drawn_as_a_scene_the_policy_accepts(name: str) -> None:
    figure = compile_figure(EXAMPLES[name], beat_seconds=BEATS)
    report = check_scene_source(figure.source)
    assert report.ok, [violation.message for violation in report.violations]
    artifact = inspect_scene("scn_1", "A figure.", figure.source)
    assert artifact.interactive is figure.interactive
    assert figure.interactive is (name in OPERATED)
    if figure.interactive:
        assert artifact.controls == OPERATED[name]


def test_there_is_an_example_of_every_kind() -> None:
    assert {example["kind"] for example in EXAMPLES.values()} == set(FIGURE_KINDS)


def test_the_figures_the_player_runs_are_what_the_module_writes() -> None:
    files = {path.name: path.read_text(encoding="utf-8") for path in FIGURES.glob("*.py")}
    assert files == written(), "Run `npm run figures` and commit what it writes."


# -- what a formula may be ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("formula", "x", "expected"),
    [
        ("2x", 3, 6),
        ("x^2 + 1", 2, 5),
        ("x**2", 3, 9),
        ("exp(-x)", 0, 1),
        ("2pi", 0, 2 * math.pi),
        ("(x+1)(x-1)", 3, 8),
        ("sqrt(x) + abs(-x)", 4, 6),
        ("ln(e)", 0, 1),
        ("1e-3 * x", 1000, 1),
        ("tanh(x)", 0, 0),
        ("0.5 * (1 + erf(x / sqrt(2)))", 0, 0.5),
        ("log10(x) + log2(x)", 100, 2 + math.log2(100)),
        ("-x", 2, -2),
    ],
)
def test_a_formula_is_read_as_arithmetic(formula: str, x: float, expected: float) -> None:
    value = _function(_python_expression(formula, None))(x, 0)
    assert value == pytest.approx(expected)


def test_the_sliders_name_may_be_used_in_a_formula() -> None:
    value = _function(_python_expression("exp(-(x - mu)^2 / 2)", "mu"))(1, 1)
    assert value == pytest.approx(1)


@pytest.mark.parametrize(
    "formula",
    [
        "__import__('os')",
        "x.__class__",
        "open('f')",
        "lambda: 1",
        "[x for x in y]",
        "y + 1",
        "x if x else 1",
        "max(x, 1)",
        "sin(x, 2)",
        "x; 1",
        "'text'",
        "x" * 200,
    ],
)
def test_anything_but_arithmetic_is_refused(formula: str) -> None:
    with pytest.raises(FigureError):
        _python_expression(formula, None)


def test_a_curve_without_a_value_where_it_is_drawn_is_refused() -> None:
    for formula in ("log(x)", "1/x", "sqrt(x - 1)"):
        figure = {"kind": "graph", "x": [-1, 2], "curves": [{"f": formula}]}
        with pytest.raises(FigureError, match="no value"):
            compile_figure(figure, beat_seconds=BEATS)
    # Drawn only where it has one, the same curve is fine.
    fine = {"kind": "graph", "x": [0, 4], "curves": [{"f": "log(x)", "from": 0.5}]}
    assert compile_figure(fine, beat_seconds=BEATS).kind == "graph"


# -- what a figure may say ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"steps": ["x"]},
        {"steps": [r"\href{https://example.com}{x}", "y"]},
        {"steps": [r"\def\x{1} \x", "y"]},
        {"steps": ["{x", "y"]},
        {"steps": ["x % comment", "y"]},
        {"steps": ["a"] * 11},
    ],
)
def test_an_equation_that_could_not_be_drawn_safely_is_refused(change: dict[str, Any]) -> None:
    figure = {**copy.deepcopy(EXAMPLES["equation"]), **change}
    with pytest.raises(FigureError):
        compile_figure(figure, beat_seconds=BEATS)


def test_text_is_put_into_the_scene_as_text_and_nothing_else() -> None:
    hostile = 'Go"); window.close(); ("'
    figure = {"kind": "flow", "steps": [hostile[:28], "Next"]}
    source = compile_figure(figure, beat_seconds=BEATS).source
    assert check_scene_source(source).ok
    tree = ast.parse(source)
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "close" not in called
    assert any(
        isinstance(node, ast.Constant) and "window.close()" in str(node.value)
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize(
    ("kind", "change", "problem"),
    [
        ("bars", {"values": [1, 2]}, "different number"),
        ("bars", {"highlight": 5}, "not there"),
        ("layers", {"path": [1, 9, 1]}, "one node in each layer"),
        ("table", {"rows": [["1", "2"]]}, "different number of cells"),
        ("tree", {"nodes": [{"label": "A"}, {"label": "B", "parent": 3}]}, "earlier node"),
        ("number_line", {"marks": [{"at": 9}]}, "off the number line"),
        ("graph", {"shade": {"curve": 2, "from": 0, "to": 1}}, "names a curve"),
        ("graph", {"points": [{"x": 9}]}, "off its curve"),
        ("graph", {"slider": {"name": "a", "min": 0, "max": 1, "value": 3}}, "between its ends"),
    ],
)
def test_a_figure_that_does_not_hold_together_says_why(
    kind: str, change: dict[str, Any], problem: str
) -> None:
    source = next(example for example in EXAMPLES.values() if example["kind"] == kind)
    figure = {**copy.deepcopy(source), **change}
    with pytest.raises(FigureError, match=problem):
        compile_figure(figure, beat_seconds=BEATS)


def test_an_unknown_kind_or_a_missing_field_is_said_plainly() -> None:
    with pytest.raises(FigureError, match="not a kind of figure"):
        compile_figure({"kind": "hologram"}, beat_seconds=BEATS)
    with pytest.raises(FigureError, match="steps"):
        compile_figure({"kind": "equation"}, beat_seconds=BEATS)
    with pytest.raises(FigureError):
        compile_figure("an equation", beat_seconds=BEATS)


# -- how a figure moves ------------------------------------------------------------------------


def test_a_figure_lasts_as_long_as_what_is_said_over_it() -> None:
    # One step a beat, and the last step holds for what is left.
    holds = _paced(2, [4.0, 5.0, 6.0], 1.0)
    assert holds == [3.0, 10.0]
    # More steps than beats share the time out; a quick part still lets each step be seen.
    assert _paced(4, [8.0], 1.0) == [1.0, 1.0, 1.0, 1.0]
    assert all(hold >= 0.4 for hold in _paced(6, [1.5], 1.2))


def test_an_equation_is_split_where_a_term_can_be_seen_to_stay() -> None:
    assert _tex_parts(r"E[X] = \int_0^1 2x^2 \, dx") == ["E[X]", "=", r"\int_0^1 2x^2 \, dx"]
    assert _tex_parts(r"x^2 + 2x - 1") == ["x^2", "+", "2x", "-", "1"]
    # Never inside braces, so that each part is a formula of its own.
    assert _tex_parts(r"\frac{a+b}{c} = e^{-x}") == [r"\frac{a+b}{c}", "=", "e^{-x}"]
    assert _tex_parts(r"-x") == ["-x"]


# -- what a model writes, taken as it means it (a real lesson, 2026-11-22) ---------------------

LINE = {"kind": "graph", "x": [0, 2], "curves": [{"f": "x"}, {"f": "x^2"}]}


def test_a_field_left_blank_is_no_field() -> None:
    blank = {**LINE, "x_label": "", "y_label": " ", "curves": [{"f": "x", "label": ""}]}
    plain = {**LINE, "curves": [{"f": "x"}]}
    drawn = compile_figure(blank, beat_seconds=BEATS).source
    assert drawn == compile_figure(plain, beat_seconds=BEATS).source


def test_curves_counted_from_zero_are_understood() -> None:
    from_zero = {
        **LINE,
        "shade": {"curve": 1, "from": 0, "to": 1},
        "points": [{"x": 1, "curve": 0}],
    }
    from_one = {**LINE, "shade": {"curve": 2, "from": 0, "to": 1}, "points": [{"x": 1, "curve": 1}]}
    assert (
        compile_figure(from_zero, beat_seconds=BEATS).source
        == compile_figure(from_one, beat_seconds=BEATS).source
    )
    # A curve not named is the first, however the others are counted.
    one = {"kind": "graph", "x": [0, 2], "curves": [{"f": "x"}]}
    compile_figure(
        {**one, "shade": {"curve": 0, "from": 0, "to": 1}, "points": [{"x": 1}]}, beat_seconds=BEATS
    )
    with pytest.raises(FigureError, match="names a curve there is not"):
        compile_figure({**one, "shade": {"curve": 3, "from": 0, "to": 1}}, beat_seconds=BEATS)


@pytest.mark.parametrize(
    ("formula", "values"),
    [
        ("0.1 * (x >= 0 && x <= 10)", [0.0, 0.1, 0.1, 0.1, 0.0]),
        ("(x < 0) * 0 + (x >= 0 && x <= 10) * x / 10 + (x > 10) * 1", [0.0, 0.0, 0.5, 1.0, 1.0]),
        (
            "(x >= 0) * (1 - exp(-x))",
            [0.0, 0.0, 1 - math.exp(-5), 1 - math.exp(-10), 1 - math.exp(-11)],
        ),
        ("0 <= x <= 5", [0.0, 1.0, 1.0, 0.0, 0.0]),
        ("(x < 0 or x > 10) * 2", [2.0, 0.0, 0.0, 0.0, 2.0]),
    ],
)
def test_a_curve_in_pieces_is_written_with_comparisons(formula: str, values: list[float]) -> None:
    function = _function(_python_expression(formula, None))
    found = [function(x, 0.0) for x in (-1.0, 0.0, 5.0, 10.0, 11.0)]
    assert found == pytest.approx(values)


@pytest.mark.parametrize("formula", ["x == 1", "x = 1", "x != 1", "!x", "x & 1"])
def test_only_these_comparisons_are_read(formula: str) -> None:
    with pytest.raises(FigureError):
        _python_expression(formula, None)


def test_a_shaded_area_can_follow_the_slider() -> None:
    figure = compile_figure(EXAMPLES["graph_area_follows"], beat_seconds=BEATS)
    assert figure.interactive
    # Its far end is the slider's: None in the scene, which draws it where the slider is.
    assert "shade = [0, 0.0, None, 'F(a)', -1.0, 5.0]" in figure.source
    follows = EXAMPLES["graph_area_follows"]
    for wrong in ({"from": 0, "to": "b"}, {"from": "a", "to": "a"}):
        with pytest.raises(FigureError):
            compile_figure({**follows, "shade": wrong}, beat_seconds=BEATS)
    # Without a slider there is nothing to follow.
    alone = {key: value for key, value in follows.items() if key != "slider"}
    with pytest.raises(FigureError):
        compile_figure(alone, beat_seconds=BEATS)


def test_a_slider_that_moves_x_is_a_point_running_along_the_curve() -> None:
    moving = {**LINE, "slider": {"name": "x", "min": 0, "max": 2, "value": 1}}
    figure = compile_figure(moving, beat_seconds=BEATS)
    assert not figure.interactive
    assert "where.animate.set_value" in figure.source


@pytest.mark.parametrize("name", ["e", "pi", "exp", "and"])
def test_a_slider_cannot_take_a_name_a_formula_already_uses(name: str) -> None:
    with pytest.raises(FigureError):
        compile_figure(
            {**LINE, "slider": {"name": name, "min": 0, "max": 1, "value": 0}}, beat_seconds=BEATS
        )


def assigned(source: str, name: str) -> Any:
    """The value a scene gives a name, read back from the scene."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(name)


def test_a_table_cell_may_hold_words_and_formulas_together() -> None:
    rows = assigned(compile_figure(EXAMPLES["table_words"], beat_seconds=BEATS).source, "rows")
    assert rows[1] == [
        [False, "Never falls"],
        [True, r"\text{If } a < b \text{ then } F(a) \le F(b)"],
    ]
    # The words are words in the formula: what TeX would read in them is taken out.
    table = {"kind": "table", "header": ["a"], "rows": [[r"50% of {all} $x$"]]}
    cells = assigned(compile_figure(table, beat_seconds=BEATS).source, "rows")
    assert cells == [[[True, r"\text{50\% of all } x"]]]
    with pytest.raises(FigureError, match="without its pair"):
        compile_figure({"kind": "table", "header": ["a"], "rows": [["$x"]]}, beat_seconds=BEATS)


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_every_figure_can_be_said_in_words_from_its_data(name: str) -> None:
    """What stands for a figure the model did not describe: text a lesson can hold, with
    its formulas closed, naming what is drawn."""
    described = compile_figure(EXAMPLES[name], beat_seconds=BEATS).described
    TypeAdapter(LongDisplay).validate_python(described)
    assert described.endswith(".")
    assert described.count("$") % 2 == 0


def test_a_formula_escaped_twice_is_drawn_as_it_was_meant() -> None:
    line = {
        "kind": "number_line",
        "from": 0,
        "to": 10,
        "interval": {"from": 2, "to": 5, "label": r"P(a < X \\le b)"},
    }
    interval = assigned(compile_figure(line, beat_seconds=BEATS).source, "interval")
    assert interval[2] == r"P(a < X \le b)"


def test_a_cumulative_curve_shows_a_probability_as_how_much_it_rises() -> None:
    """A real lesson shaded the area under a cumulative curve and called it a probability
    (2026-11-22). The area under a density is one; on a cumulative curve it is a rise."""
    figure = compile_figure(EXAMPLES["graph_rise"], beat_seconds=BEATS)
    rises = assigned(figure.source, "rises")
    assert [rise[:3] for rise in rises] == [[0, 0.0, 2.0], [0, 5.0, 8.0]]
    assert "how much it rises from $5$ to $8$ marked" in figure.described
    # One rise, as a model also writes it, is a list of one.
    one = compile_figure(
        {**EXAMPLES["graph_rise"], "rise": {"from": 2, "to": 5}}, beat_seconds=BEATS
    )
    assert [rise[:3] for rise in assigned(one.source, "rises")] == [[0, 2.0, 5.0]]
    many = {**EXAMPLES["graph_rise"], "rise": [{"from": 0, "to": 1}] * 4}
    with pytest.raises(FigureError, match="rise"):
        compile_figure(many, beat_seconds=BEATS)
    outside = {**EXAMPLES["graph_rise"], "rise": {"from": 2, "to": 15}}
    with pytest.raises(FigureError, match="rise"):
        compile_figure(outside, beat_seconds=BEATS)
    flat = {**EXAMPLES["graph_rise"], "rise": {"from": 3, "to": 3}}
    with pytest.raises(FigureError, match="rise"):
        compile_figure(flat, beat_seconds=BEATS)


# -- what a real model wrote, again (2026-11-22) -------------------------------------------------
#
# A lesson on a chapter about distributions, written by Nemotron 3 Ultra at "medium": five
# figures written, one drawn. Each of these is the shape of one that was lost.


def test_a_step_of_an_equation_may_say_something_in_words_beside_its_formula() -> None:
    figure = {
        "kind": "equation",
        "steps": [r"$F(x) = P(X \le x)$", "$F$ is non-decreasing", "F is right-continuous"],
    }
    parts = assigned(compile_figure(figure, beat_seconds=BEATS).source, "parts")
    assert parts[1] == [r"\displaystyle F \text{ is non-decreasing}"]
    assert parts[2] == [r"\displaystyle F \text{ is right-continuous}"]


def test_a_function_given_piece_by_piece_may_take_more_steps() -> None:
    steps = [r"F(x) = 0 \quad (x < 1)"]
    steps += [rf"F(x) = {k}/6 \quad ({k} \le x < {k + 1})" for k in range(1, 6)]
    steps += [r"F(x) = 1 \quad (x \ge 6)"]
    figure = {"kind": "equation", "steps": steps}
    assert len(assigned(compile_figure(figure, beat_seconds=BEATS).source, "parts")) == 7


def test_a_curve_flat_over_most_of_where_it_is_drawn_is_not_taken_for_a_pole() -> None:
    """A uniform distribution's cumulative curve with its width on a slider: at its least
    width the curve is flat almost everywhere, and its one climb looked like a jump."""
    figure = {
        "kind": "graph",
        "x": [-1, 21],
        "curves": [{"f": "(x<0)*0 + (x>=0)*(x<=b)*(x/b) + (x>b)*1", "label": "F(x)"}],
        "slider": {"name": "b", "label": "b", "min": 1, "max": 20, "value": 10},
    }
    assert compile_figure(figure, beat_seconds=BEATS).interactive
    # A step where a comparison changes, as a die's cumulative curve has six of.
    die = " + ".join(f"(x >= {k}) / 6" for k in range(1, 7))
    steps = {"kind": "graph", "x": [0, 7], "curves": [{"f": die}]}
    assert compile_figure(steps, beat_seconds=BEATS).kind == "graph"
    # A pole is still refused, wherever the samples fall.
    for formula, span in (("1/(x - 0.3)", [-1, 2]), ("tan(x)", [0, 3]), ("1/x^2", [-1, 2])):
        pole = {"kind": "graph", "x": span, "curves": [{"f": formula}]}
        with pytest.raises(FigureError, match="no value"):
            compile_figure(pole, beat_seconds=BEATS)


def test_words_in_a_formula_are_set_as_words_and_symbols_as_tex() -> None:
    figure = {
        "kind": "graph",
        "x": [-1, 11],
        "curves": [{"f": "(x >= 0 && x <= 10) * x / 10 + (x > 10) * 1", "label": "Uniform CDF"}],
        "rise": [{"from": 0, "to": 3, "label": "P(X" + chr(0x2264) + "3)=0.3"}],
        "x_label": "x",
        "y_label": chr(0x03C3) + "^2",
    }
    compiled = compile_figure(figure, beat_seconds=BEATS)
    assert r"$\text{Uniform CDF}$" in compiled.described
    assert assigned(compiled.source, "rises")[0][3] == r"P(X \le 3)=0.3"
    assert r"\sigma ^2" in compiled.source
    # A function TeX has a command for is set by it; a command is left as it is.
    exponential = {"kind": "graph", "x": [0, 3], "curves": [{"f": "exp(-x)", "label": "exp(-x)"}]}
    assert r"\exp (-x)" in compile_figure(exponential, beat_seconds=BEATS).source
    named = {**exponential, "curves": [{"f": "exp(-x)", "label": r"\operatorname{Var}(X)"}]}
    assert r"\operatorname{Var}(X)" in compile_figure(named, beat_seconds=BEATS).source


@pytest.mark.parametrize(
    ("formula", "values"),
    [
        ("(x >= 0 && x <= 1) ? 2*x : 0", [0.0, 1.0, 0.0]),
        ("x < 0 ? 0 : x < 1 ? x : 1", [0.0, 0.5, 1.0]),
        ("x > 0 ? (x < 1 ? x : 1) : 0", [0.0, 0.5, 1.0]),
    ],
)
def test_a_choice_between_two_values_is_read_as_a_model_writes_it(
    formula: str, values: list[float]
) -> None:
    fn = _function(_python_expression(formula, None))
    assert [fn(x, 0) for x in (-0.5, 0.5, 1.5)] == values


@pytest.mark.parametrize("formula", ["x ? 1", "? 1 : 0", "x : 1", "x ? : 1", "x ? 1 :"])
def test_a_choice_that_is_not_whole_is_refused(formula: str) -> None:
    with pytest.raises(FigureError, match="could not be read"):
        _python_expression(formula, None)


def test_a_label_may_say_something_in_words_beside_its_formula() -> None:
    figure = {
        "kind": "graph",
        "x": [-1, 3],
        "curves": [{"f": "(x>=0 && x<=2) * 0.5", "label": "$f(x) = 1/2$ on [0, 2]"}],
    }
    described = compile_figure(figure, beat_seconds=BEATS).described
    assert r"$f(x) = 1/2 \text{ on [0, 2]}$" in described


def test_an_area_shaded_under_a_cumulative_curve_is_drawn_as_how_much_it_rises() -> None:
    """A lesson written without thinking shaded the area under F(x) and called it a
    probability (2026-11-22). Under a curve the figure calls cumulative, a probability is
    how much it rises: that is what is drawn, and what is said of it."""
    cdf = {
        "kind": "graph",
        "x": [-1, 11],
        "curves": [{"f": "(x >= 0 && x <= 10) ? x/10 : (x < 0 ? 0 : 1)", "label": "F_X(x)"}],
        "shade": {"from": 2, "to": 7, "label": r"P(2 \le X \le 7)"},
    }
    compiled = compile_figure(cdf, beat_seconds=BEATS)
    assert compiled.mended
    assert assigned(compiled.source, "shade") is None
    assert [rise[:3] for rise in assigned(compiled.source, "rises")] == [[0, 2.0, 7.0]]
    assert "how much it rises from $2$ to $7$ marked" in compiled.described
    # Under a density the area is the probability, and it stays as written.
    density = {**cdf, "curves": [{"f": "(x >= 0 && x <= 10) ? 0.1 : 0", "label": "f_X(x)"}]}
    kept = compile_figure(density, beat_seconds=BEATS)
    assert not kept.mended
    assert assigned(kept.source, "shade")[1:3] == [2.0, 7.0]
    # Called cumulative, but falling: not one, and left as written.
    falling = {**cdf, "x": [0, 10], "curves": [{"f": "1 - x/10", "label": "F(x)"}]}
    assert not compile_figure(falling, beat_seconds=BEATS).mended


def test_a_table_may_have_eight_rows_and_no_more() -> None:
    """A real lesson's table of a network's values had seven rows (2026-11-22)."""
    eight = {**EXAMPLES["table"], "rows": [["1", "2", "3"]] * 8, "highlight": [8]}
    assert compile_figure(eight, beat_seconds=BEATS).kind == "table"
    with pytest.raises(FigureError, match="rows"):
        compile_figure({**eight, "rows": [["1", "2", "3"]] * 9}, beat_seconds=BEATS)


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_every_figure_says_how_it_is_laid_out_as_each_page_ends(name: str) -> None:
    source = compile_figure(EXAMPLES[name], beat_seconds=BEATS).source
    tree = ast.parse(source)
    scene = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    methods = {node.name: node for node in scene.body if isinstance(node, ast.FunctionDef)}
    assert {"words_of", "meet", "within", "audit"} <= set(methods)
    for page in ("construct", "blueprint"):
        if page not in methods:
            continue
        last = methods[page].body[-1]
        # The last thing the page does: its words and edges looked at as they are drawn.
        assert ast.unparse(last) == "self.audit()", (name, page)
