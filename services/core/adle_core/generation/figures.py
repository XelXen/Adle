"""Figures: a lesson's pictures, drawn by the core from tested templates filled with the
model's data (ADR-045).

A model that writes a whole scene file, against an animation library it knows only in part,
writes slowly and breaks often: a picture took a reasoning model two and a half minutes, and
failed its trial often enough to be written twice. Most of what a lesson needs to show is of a
few kinds: an equation rewritten step by step, a graph with an area or a point on it, bars, a
number line, a flow of steps, layers of a network, a table, a scatter of points, vectors, a
tree. The lesson's text now names the kind and gives the data, a few lines of JSON among its
other fields; the core writes the scene from a template built only from constructs that run
in the player (the end-to-end suite runs every kind), checked and bounded here first. A figure
costs no request, takes no time to draw, and cannot fail the way a model's file can.

What the model gives is data, never code. Text is put into the scene as a string literal; a
graph's formula is read by a parser that takes numbers, ``x``, one slider's name, the four
operations, powers, and a few functions, and nothing else, and is tried at hundreds of points
before it is used. The file written still passes the scene policy and runs in the player's
sandbox like any other.
"""

from __future__ import annotations

import ast
import contextlib
import itertools
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from adle_core.generation.layout import LAYOUT_METHODS
from adle_core.generation.speech import UNICODE_TEX

#: The kinds of figure there are, as the lesson format names them.
FIGURE_KINDS = (
    "equation",
    "graph",
    "bars",
    "number_line",
    "flow",
    "layers",
    "table",
    "scatter",
    "vectors",
    "tree",
)

#: The narration is read at about this many words a second (ADR-040).
WORDS_PER_SECOND = 2.5
#: The safe area of the stage (the scene guide's layout rules).
_SAFE_X = 6.2
_SAFE_Y = 3.4


class FigureError(ValueError):
    """A figure that cannot be drawn as given. Its part is said in words instead."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


# -- what may be written in a figure -----------------------------------------------------------

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
#: TeX commands that could reach outside a formula, define something, or load anything.
_TEX_FORBIDDEN = re.compile(
    r"\\(?:href|url|class|style|cssId|htmlData|require|def|edef|gdef|newcommand|"
    r"renewcommand|providecommand|let|input|include|includegraphics|catcode|csname|"
    r"unicode|mmlToken|data|Newextarrow|DeclareMathOperator)\b"
)


#: Two backslashes, and only two, before a letter: a command of TeX written twice over.
_DOUBLED = re.compile(r"(?<!\\)\\\\(?=[A-Za-z])")


def undoubled(text: str) -> str:
    r"""TeX a model escaped twice, written as it was meant.

    A real model wrote every backslash of its board text twice (2026-11-22): ``\\le``
    where ``\le`` was meant, which TeX reads as a line break and the letters "le", and
    ``\\\\`` where a row of a ``cases`` ended (``\\``). Where a command stands behind two
    backslashes, every run of them is halved. Text written once, as TeX is, is left as it
    is: a row's end followed by a space is not touched.
    """
    if not _DOUBLED.search(text):
        return text
    return re.sub(r"\\+", lambda run: "\\" * max(1, len(run.group(0)) // 2), text)


def _plain(text: str) -> str:
    text = " ".join(_CONTROL.sub(" ", text).split())
    if not text:
        raise ValueError("must say something")
    return text


def _symbols(text: str) -> str:
    """Mathematics written in its own symbols ("≤", a Greek letter) as the commands of TeX
    that say the same, outside any ``\\text{...}``: what the player's TeX is sure to set."""
    pieces = re.split(r"(\\text\{[^{}]*\})", text)
    return "".join(
        piece if index % 2 else "".join(UNICODE_TEX.get(char, char) for char in piece)
        for index, piece in enumerate(pieces)
    )


#: Where a formula already says how its letters are set, or names something (a color among
#: them: ``\color{yellow}`` is not the word "yellow" in a formula): kept as it is.
_SET = re.compile(
    r"\\(?:text|textbf|textit|mathrm|mathbf|mathit|mathsf|mathtt|mathcal|mathbb|operatorname"
    r"|mbox|begin|end|color|textcolor)\s*\{[^{}]*\}|\\[A-Za-z]+"
)
#: A word of a sentence among the letters of a formula, or a few in a row ("is
#: right-continuous"): one of three letters or more, with any words beside it.
_WORD = r"[A-Za-z]+(?:-[A-Za-z]+)*"
_WORDS = re.compile(
    rf"(?<![A-Za-z])(?:[A-Za-z]{{2,}}(?:-[A-Za-z]+)*\s+)*[A-Za-z]{{3,}}(?:-[A-Za-z]+)*"
    rf"(?:\s+{_WORD})*(?![A-Za-z])"
)
#: Functions TeX sets upright by a command of their own.
_NAMED = {
    "sin", "cos", "tan", "sec", "csc", "cot", "sinh", "cosh", "tanh", "arcsin", "arccos",
    "arctan", "exp", "log", "lim", "max", "min", "det", "gcd", "arg", "sup", "inf",
}  # fmt: skip


def _words_in(piece: str) -> str:
    def setting(match: re.Match[str]) -> str:
        words = match.group(0)
        if words in _NAMED:
            return "\\" + words + " "
        # A space beside the words stands between them and the formula: kept, as text.
        lead = " " if match.start() > 0 and piece[match.start() - 1] == " " else ""
        trail = " " if match.end() < len(piece) and piece[match.end()] == " " else ""
        return "\\text{" + lead + words + trail + "}"

    return _WORDS.sub(setting, piece)


def _words_as_text(tex: str) -> str:
    """Words in a formula set as words ("Uniform(0,10) CDF"), and the functions TeX names
    by a command as that command ("exp(-x)"): in a formula a word is otherwise a row of
    variables, in italics and without its spaces. A command, and what is already set as
    text or named, is left as it is."""
    out: list[str] = []
    at = 0
    for kept in _SET.finditer(tex):
        out.append(_words_in(tex[at : kept.start()]))
        out.append(kept.group(0))
        at = kept.end()
    out.append(_words_in(tex[at:]))
    return "".join(out)


def _tex(text: str) -> str:
    """A formula: TeX, with its dollar signs or without them, or words with formulas among
    them ("$F_X$ is non-decreasing", "$f(x) = 1/2$ on [0, 2]"), set as one formula with the
    words as text, as a cell of a table is (``_mixed``)."""
    text = " ".join(_CONTROL.sub(" ", text).split())
    for mark in ("$$", "$"):
        if len(text) > 2 * len(mark) and text.startswith(mark) and text.endswith(mark):
            inside = text[len(mark) : -len(mark)]
            if "$" not in inside:
                text = inside.strip()
                break
    if "$" in text:
        return _mixed(text)
    text = _words_as_text(" ".join(_symbols(undoubled(text)).split()))
    if not text:
        raise ValueError("must say something")
    if _TEX_FORBIDDEN.search(text):
        raise ValueError("uses a TeX command a figure may not use")
    if re.search(r"(?<!\\)%", text):
        raise ValueError("has a % that is not \\%")
    depth = 0
    for index, char in enumerate(text):
        if char == "{" and (index == 0 or text[index - 1] != "\\"):
            depth += 1
        elif char == "}" and (index == 0 or text[index - 1] != "\\"):
            depth -= 1
            if depth < 0:
                raise ValueError("has a } without its {")
    if depth != 0:
        raise ValueError("has a { without its }")
    return text


Label = Annotated[str, StringConstraints(max_length=40), AfterValidator(_plain)]
Phrase = Annotated[str, StringConstraints(max_length=28), AfterValidator(_plain)]
Tex = Annotated[str, StringConstraints(max_length=160), AfterValidator(_tex)]
ShortTex = Annotated[str, StringConstraints(max_length=60), AfterValidator(_tex)]
Number = Annotated[float, Field(allow_inf_nan=False, ge=-1e6, le=1e6)]


class _Spec(BaseModel):
    # A field the format does not know is passed over; one it knows must be right.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class EquationFigure(_Spec):
    kind: Literal["equation"]
    # One step on the stage at a time: ten is a long derivation, or a function given
    # piece by piece, and still a step for each sentence said over it.
    steps: list[Tex] = Field(min_length=2, max_length=10)


class Curve(_Spec):
    f: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    label: ShortTex | None = None
    #: Where the curve is drawn, when not over the whole of the x axis.
    start: Number | None = Field(default=None, alias="from")
    end: Number | None = Field(default=None, alias="to")


#: Where an area under a curve begins or ends: a number, or the slider's name, to follow it.
Bound = Number | Annotated[str, StringConstraints(max_length=12)]


class Shade(_Spec):
    #: Which curve, counted from 1. A model that counts from 0 is understood (``_graph``).
    curve: int = Field(default=1, ge=0, le=3)
    start: Bound = Field(alias="from")
    end: Bound = Field(alias="to")
    label: ShortTex | None = None


class GraphPoint(_Spec):
    x: Number
    curve: int = Field(default=1, ge=0, le=3)
    label: ShortTex | None = None


class Rise(_Spec):
    """How much a curve rises between two values of x: on a cumulative curve, a probability."""

    curve: int = Field(default=1, ge=0, le=3)
    start: Number = Field(alias="from")
    end: Number = Field(alias="to")
    label: ShortTex | None = None


#: Names a slider cannot have: a formula already means something by them.
_TAKEN = {
    "e", "pi", "and", "or", "sin", "cos", "tan", "exp", "log", "ln", "sqrt", "abs", "tanh",
    "sinh", "cosh", "atan", "erf", "log10", "log2",
}  # fmt: skip


def _slider_name(name: str) -> str:
    if name in _TAKEN:
        raise ValueError("is a name a formula already uses")
    return name


class GraphSlider(_Spec):
    name: Annotated[
        str,
        StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9]{0,5}$"),
        AfterValidator(_slider_name),
    ]
    label: ShortTex | None = None
    min: Number
    max: Number
    value: Number


class GraphFigure(_Spec):
    kind: Literal["graph"]
    x: list[Number] = Field(min_length=2, max_length=2)
    y: list[Number] | None = Field(default=None, min_length=2, max_length=2)
    x_label: ShortTex | None = None
    y_label: ShortTex | None = None
    curves: list[Curve] = Field(min_length=1, max_length=3)
    shade: Shade | None = None
    rise: list[Rise] = Field(default_factory=list, max_length=3)
    points: list[GraphPoint] = Field(default_factory=list, max_length=3)
    trace: bool = False
    slider: GraphSlider | None = None

    @field_validator("rise", mode="before")
    @classmethod
    def _one_or_more(cls, value: object) -> object:
        # One rise, or a list of them: a model writes either.
        if value is None:
            return []
        return [value] if isinstance(value, dict) else value


class BarsFigure(_Spec):
    kind: Literal["bars"]
    labels: list[Label] = Field(min_length=2, max_length=8)
    values: list[Number] = Field(min_length=2, max_length=8)
    then: list[Number] | None = Field(default=None, min_length=2, max_length=8)
    highlight: int | None = Field(default=None, ge=1, le=8)
    y_label: ShortTex | None = None


class Mark(_Spec):
    at: Number
    label: ShortTex | None = None


class Span(_Spec):
    start: Number = Field(alias="from")
    end: Number = Field(alias="to")
    label: ShortTex | None = None


class NumberLineFigure(_Spec):
    kind: Literal["number_line"]
    start: Number = Field(alias="from")
    end: Number = Field(alias="to")
    marks: list[Mark] = Field(default_factory=list, max_length=6)
    interval: Span | None = None
    move: Span | None = None


class FlowFigure(_Spec):
    kind: Literal["flow"]
    steps: list[Phrase] = Field(min_length=2, max_length=6)
    loop: bool = False


class Layer(_Spec):
    label: Annotated[str, StringConstraints(max_length=16), AfterValidator(_plain)]
    nodes: int = Field(ge=1, le=6)


class LayersFigure(_Spec):
    kind: Literal["layers"]
    layers: list[Layer] = Field(min_length=2, max_length=5)
    path: list[int] | None = None


Cell = Annotated[str, StringConstraints(max_length=90)]


class TableFigure(_Spec):
    kind: Literal["table"]
    header: list[Cell] = Field(min_length=1, max_length=4)
    # Each row is as tall as the stage has room for (``_table``): eight still read.
    rows: list[list[Cell]] = Field(min_length=1, max_length=8)
    highlight: list[int] = Field(default_factory=list, max_length=6)


class Fit(_Spec):
    slope: Number
    intercept: Number
    label: ShortTex | None = None


class ScatterFigure(_Spec):
    kind: Literal["scatter"]
    points: list[list[Number]] = Field(min_length=3, max_length=40)
    line: Fit | None = None
    residuals: bool = False
    x_label: ShortTex | None = None
    y_label: ShortTex | None = None


class Vector(_Spec):
    x: Number
    y: Number
    label: ShortTex | None = None


class VectorsFigure(_Spec):
    kind: Literal["vectors"]
    vectors: list[Vector] = Field(min_length=1, max_length=3)
    sum: bool = False


class TreeNode(_Spec):
    label: Annotated[str, StringConstraints(max_length=14), AfterValidator(_plain)]
    parent: int | None = Field(default=None, ge=1)
    edge: ShortTex | None = None


class TreeFigure(_Spec):
    kind: Literal["tree"]
    nodes: list[TreeNode] = Field(min_length=2, max_length=15)


Figure = Annotated[
    EquationFigure
    | GraphFigure
    | BarsFigure
    | NumberLineFigure
    | FlowFigure
    | LayersFigure
    | TableFigure
    | ScatterFigure
    | VectorsFigure
    | TreeFigure,
    Field(discriminator="kind"),
]
_FIGURE: TypeAdapter[Any] = TypeAdapter(Figure)


@dataclass(frozen=True, slots=True)
class CompiledFigure:
    kind: str
    #: The whole scene file.
    source: str
    #: It has a control the learner operates.
    interactive: bool
    #: What it shows, in words, said by Adle from its data: for a figure the model did not
    #: describe, so that it still has a text to stand for it (``describe``).
    described: str
    #: Drawn otherwise than written (``_rise_for_shade``): the model's own words for it
    #: describe what is not drawn, and Adle's are used instead.
    mended: bool = False


def _without_blanks(value: Any) -> Any:
    """What a model wrote, without the fields it left empty: ``"y_label": ""`` is no label,
    not a figure that is wrong. (A table's empty cell is a list's item and stays.)"""
    if isinstance(value, dict):
        return {
            key: _without_blanks(item)
            for key, item in value.items()
            if not (item is None or (isinstance(item, str) and not item.strip()))
        }
    if isinstance(value, list):
        return [_without_blanks(item) for item in value]
    return value


def read_figure(raw: object) -> Any:
    """A figure as the model wrote it, checked, or ``FigureError`` saying what is wrong."""
    if not isinstance(raw, dict):
        raise FigureError(["a figure is an object with a kind"])
    written: dict[str, Any] = _without_blanks(raw)
    kind = str(written.get("kind", "")).strip().lower().replace("-", "_").replace(" ", "_")
    if kind not in FIGURE_KINDS:
        raise FigureError([f'"{kind[:30]}" is not a kind of figure'])
    try:
        return _FIGURE.validate_python({**written, "kind": kind})
    except ValidationError as error:
        problems = []
        for item in error.errors(include_input=False, include_url=False):
            where = ".".join(str(part) for part in item["loc"][1:]) or kind
            problems.append(f"{where}: {item['msg']}")
        raise FigureError(problems[:8]) from error


#: A curve named as a cumulative one: F(x), F_X(x), a CDF. A density is f, in lower case.
_NAMED_CUMULATIVE = re.compile(r"(?<![A-Za-z\\])F\s*(?:_|\(|\\left\()")
_SAID_CUMULATIVE = re.compile(r"\bCDF\b|cumulative", re.IGNORECASE)


def _is_cumulative(figure: GraphFigure, index: int) -> bool:
    """Whether a curve of a graph is a cumulative distribution: named as one, never falling,
    and running between 0 and 1."""
    if not 0 <= index < len(figure.curves):
        return False
    curve = figure.curves[index]
    words = " ".join(text for text in (curve.label, figure.y_label) if text)
    if not (_NAMED_CUMULATIVE.search(words) or _SAID_CUMULATIVE.search(words)):
        return False
    slider = figure.slider if figure.slider is not None and figure.slider.name != "x" else None
    x0, x1 = sorted(figure.x)
    start = x0 if curve.start is None else max(x0, curve.start)
    end = x1 if curve.end is None else min(x1, curve.end)
    try:
        value = _function(_python_expression(curve.f, slider.name if slider else None))
        heights = [value(x, slider.value if slider else 0.0) for x in _samples(start, end)]
    except (FigureError, ValueError, ZeroDivisionError, OverflowError):
        return False
    if not all(math.isfinite(height) for height in heights):
        return False
    rising = all(after >= before - 1e-9 for before, after in itertools.pairwise(heights))
    low, high = min(heights), max(heights)
    return rising and low >= -0.02 and high <= 1.02 and high - low >= 0.3


def _rise_for_shade(figure: GraphFigure) -> tuple[GraphFigure, bool]:
    """A probability is the area under a density; on a cumulative curve it is how much the
    curve rises. A model that shades under a curve it calls cumulative means the rise, and
    the area would be a wrong picture of it: it is drawn as the rise (ADR-045). Whether it
    was."""
    shade = figure.shade
    if shade is None or len(figure.rise) >= 3:
        return figure, False
    items: list[Shade | Rise | GraphPoint] = [shade, *figure.rise, *figure.points]
    named = [item for item in items if "curve" in item.model_fields_set]
    first = 0 if any(item.curve == 0 for item in named) else 1
    index = shade.curve - first if "curve" in shade.model_fields_set else 0
    try:
        ends = [float(shade.start), float(shade.end)]
    except ValueError:
        return figure, False  # an end follows the slider: a rise cannot
    if not _is_cumulative(figure, index):
        return figure, False
    written: dict[str, Any] = {"from": ends[0], "to": ends[1]}
    if shade.label:
        written["label"] = shade.label
    if "curve" in shade.model_fields_set:
        written["curve"] = shade.curve
    rise = Rise.model_validate(written)
    return figure.model_copy(update={"shade": None, "rise": [*figure.rise, rise]}), True


def compile_figure(raw: object, *, beat_seconds: Sequence[float]) -> CompiledFigure:
    """The scene file for a figure, paced to the beats said over it."""
    figure = read_figure(raw)
    mended = False
    if isinstance(figure, GraphFigure):
        figure, mended = _rise_for_shade(figure)
    beats = [max(1.5, float(seconds)) for seconds in beat_seconds] or [6.0]
    writers: dict[str, Callable[[Any, list[float]], tuple[str, bool]]] = {
        "equation": _equation,
        "graph": _graph,
        "bars": _bars,
        "number_line": _number_line,
        "flow": _flow,
        "layers": _layers,
        "table": _table,
        "scatter": _scatter,
        "vectors": _vectors,
        "tree": _tree,
    }
    source, interactive = writers[figure.kind](figure, beats)
    return CompiledFigure(
        kind=figure.kind,
        source=_audited(source),
        interactive=interactive,
        described=describe(figure),
        mended=mended,
    )


# -- a figure in words -------------------------------------------------------------------------


def _math(tex: str | None) -> str:
    return f"${tex}$" if tex else ""


def _number(value: float) -> str:
    return f"${value:g}$"


def _words(text: str) -> str:
    """Plain words from a figure, with nothing a formula would be read from."""
    return " ".join(text.replace("$", "").split())


def _listed(items: Sequence[str]) -> str:
    items = [item for item in items if item]
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def describe(figure: Any) -> str:
    """What a figure shows, in words, from its data alone: plain, and never more than it
    shows. It stands for the picture where the model gave no description of its own (a
    real model left out all five, 2026-11-22), and is what a learner reads when the picture
    is not seen."""
    kind = figure.kind
    if kind == "equation":
        return (
            f"The formula {_math(figure.steps[0])} is rewritten step by step until it reads "
            f"{_math(figure.steps[-1])}."
        )
    if kind == "graph":
        names = [_math(curve.label) for curve in figure.curves if curve.label]
        what = _listed(names) or ("a curve" if len(figure.curves) == 1 else "curves")
        low, high = sorted(figure.x)
        axis = _math(figure.x_label) or "$x$"
        said = f"A graph of {what} for {axis} from {_number(low)} to {_number(high)}"
        extras = []
        if figure.shade is not None:
            ends = [
                "the slider's value" if isinstance(end, str) else _number(end)
                for end in (figure.shade.start, figure.shade.end)
            ]
            extras.append(
                f"the area under it from {ends[0]} to {ends[1]} shaded"
                + (f" ({_math(figure.shade.label)})" if figure.shade.label else "")
            )
        for rise in figure.rise:
            extras.append(
                f"how much it rises from {_number(rise.start)} to {_number(rise.end)} marked"
                + (f" ({_math(rise.label)})" if rise.label else "")
            )
        if figure.points:
            extras.append(
                "points marked at "
                + _listed([_math(point.label) or _number(point.x) for point in figure.points])
            )
        # A slider that moves x is drawn as a point running along the curve (``_graph``).
        moves_x = figure.slider is not None and figure.slider.name == "x"
        if figure.trace or moves_x:
            extras.append("a point that runs along the curve")
        if figure.slider is not None and not moves_x:
            name = _math(figure.slider.label) or _words(figure.slider.name)
            span = sorted((figure.slider.min, figure.slider.max))
            extras.append(f"a slider for {name} from {_number(span[0])} to {_number(span[1])}")
        return said + (", with " + _listed(extras) if extras else "") + "."
    if kind == "bars":
        pairs = [
            f"{_words(label)}: {_number(value)}"
            for label, value in zip(figure.labels, figure.values, strict=False)
        ]
        said = "Bars for " + _listed(pairs)
        if figure.then:
            said += ", which change to " + _listed([_number(value) for value in figure.then])
        return said + "."
    if kind == "number_line":
        low, high = sorted((figure.start, figure.end))
        said = f"A number line from {_number(low)} to {_number(high)}"
        extras = []
        if figure.marks:
            extras.append(
                "marks at "
                + _listed([_math(mark.label) or _number(mark.at) for mark in figure.marks])
            )
        if figure.interval is not None:
            extras.append(
                f"the stretch from {_number(figure.interval.start)} to "
                f"{_number(figure.interval.end)} picked out"
                + (f" ({_math(figure.interval.label)})" if figure.interval.label else "")
            )
        if figure.move is not None:
            extras.append(
                f"a point that moves from {_number(figure.move.start)} to {_number(figure.move.end)}"
            )
        return said + (", with " + _listed(extras) if extras else "") + "."
    if kind == "flow":
        steps = [_words(step) for step in figure.steps]
        return (
            "Steps in order: "
            + ", then ".join(steps)
            + (", and back to the first." if figure.loop else ".")
        )
    if kind == "layers":
        layers = [f"{_words(layer.label)} ({layer.nodes})" for layer in figure.layers]
        return "Layers of nodes, each joined to the next: " + _listed(layers) + "."
    if kind == "table":
        header = [_words(cell) for cell in figure.header]
        rows = len(figure.rows)
        return f"A table with the columns {_listed(header)}, and {rows} " + (
            "row." if rows == 1 else "rows."
        )
    if kind == "scatter":
        said = f"{len(figure.points)} points"
        if figure.line is not None:
            said += " and a line through them" + (
                f" ({_math(figure.line.label)})" if figure.line.label else ""
            )
            if figure.residuals:
                said += ", with how far each point is from it"
        return said + "."
    if kind == "vectors":
        arrows = [
            (_math(vector.label) or "a vector") + f" to $({vector.x:g}, {vector.y:g})$"
            for vector in figure.vectors
        ]
        return (
            "Arrows from the origin: "
            + _listed(arrows)
            + (", and their sum, added tip to tail." if figure.sum and len(arrows) > 1 else ".")
        )
    if kind == "tree":
        root = _words(figure.nodes[0].label)
        rest = [_words(node.label) for node in figure.nodes[1:]]
        return f"A tree from {root}, branching to " + _listed(rest) + "."
    return "A figure."


def beat_seconds(texts: Sequence[str]) -> list[float]:
    """How long each beat is said for, at the narration's pace."""
    return [len(text.split()) / WORDS_PER_SECOND for text in texts]


# -- writing a scene ---------------------------------------------------------------------------


def _py(value: object) -> str:
    """A value as a literal in the scene's Python."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        rounded = round(value, 6)
        return repr(0.0 if rounded == 0 else rounded)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_py(item) for item in value) + "]"
    raise TypeError(type(value).__name__)


_PALETTE = """\
    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"
"""


def _scene(name: str, doc: str, body: str, *, interactive: bool = False) -> str:
    base = "InteractiveScene" if interactive else "Scene"
    head = "from manim import *\nimport math\n\n\n"
    return f'{head}class {name}({base}):\n    """{doc}"""\n\n{_PALETTE}\n{body}'


def _audited(source: str) -> str:
    """A figure that says, as its animation ends and as its live page opens, whether any of
    its words lie over others or anything lies past the edge of the screen (ADR-055)."""
    lines = source.rstrip("\n").split("\n")
    ends: list[int] = []
    inside = False
    for index, line in enumerate(lines):
        if line.startswith("    def "):
            if inside:
                ends.append(index)
            inside = line.startswith(("    def construct(self)", "    def blueprint(self)"))
    if inside:
        ends.append(len(lines))
    for end in reversed(ends):
        while end > 0 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, "        self.audit()")
    return "\n".join(lines) + "\n\n" + LAYOUT_METHODS


def _paced(steps: int, beats: list[float], play: float) -> list[float]:
    """How long to hold after each of ``steps`` animations of ``play`` seconds, so that the
    figure lasts as long as what is said over it and moves on as the beats do."""
    total = max(sum(beats), steps * (play + 0.6))
    if steps <= len(beats):
        # One step a beat, the last beats shared out among the last step.
        slots = [*beats[: steps - 1], sum(beats[steps - 1 :])]
    else:
        slots = [total / steps] * steps
    scale = total / max(sum(slots), 0.1)
    return [round(max(0.4, slot * scale - play), 2) for slot in slots]


def _visible(tex: str) -> int:
    """About how many characters wide a formula is drawn: commands count as one."""
    stripped = re.sub(r"\\[A-Za-z]+", "x", tex)
    stripped = re.sub(r"[{}_^\\ ]", "", stripped)
    return max(1, len(stripped))


def _formula_size(texts: Sequence[str], largest: int = 48, smallest: int = 34) -> int:
    """The largest size at which the widest formula fits the stage, but never below 34."""
    widest = max(_visible(text) for text in texts)
    for size in range(largest, smallest - 1, -2):
        if widest * 0.27 * size / 48 <= 2 * _SAFE_X - 0.4:
            return size
    return smallest


def _tex_parts(tex: str) -> list[str]:
    """A formula split where an equals sign or a plus or minus between terms stands, so
    that a part kept from one step to the next is seen to stay (TransformMatchingTex)."""
    parts: list[str] = []
    depth = 0
    current = ""
    index = 0
    while index < len(tex):
        char = tex[index]
        if tex.startswith("\\left", index):
            depth += 1
        elif tex.startswith("\\right", index):
            depth -= 1
        if char == "{" and (index == 0 or tex[index - 1] != "\\"):
            depth += 1
        elif char == "}" and (index == 0 or tex[index - 1] != "\\"):
            depth -= 1
        if (
            depth == 0
            and char in "=+-"
            and current.strip()
            and (index == 0 or tex[index - 1] != "\\")
        ):
            parts.append(current.strip())
            parts.append(char)
            current = ""
        else:
            current += char
        index += 1
    if current.strip():
        parts.append(current.strip())
    return parts[:24] or [tex]


# -- equation ----------------------------------------------------------------------------------


def _equation(figure: EquationFigure, beats: list[float]) -> tuple[str, bool]:
    size = _formula_size(figure.steps)
    holds = _paced(len(figure.steps), beats, 1.4)
    # In display style, as a formula on a page of its own: a fraction or a sum full size.
    steps = [[rf"\displaystyle {part}" for part in _tex_parts(step)] for step in figure.steps]
    body = f"""\
    def construct(self):
        parts = {_py(steps)}
        holds = {_py(holds)}
        steps = []
        for each in parts:
            step = MathTex(*each, font_size={size}, color=self.ink)
            step.move_to([0, 0.2, 0])
            steps.append(step)
        self.play(Write(steps[0]), run_time=1.4)
        self.wait(holds[0])
        for index in range(1, len(steps)):
            self.play(TransformMatchingTex(steps[index - 1], steps[index]), run_time=1.4)
            self.wait(holds[index])
        frame = SurroundingRectangle(steps[len(steps) - 1], color=self.sun, buff=0.2)
        self.play(Create(frame), run_time=0.6)
        self.play(FadeOut(frame), run_time=0.5)
"""
    return _scene("EquationFigure", "A formula rewritten one step at a time.", body), False


# -- graph -------------------------------------------------------------------------------------

_FUNCTIONS = {
    "sin": "math.sin",
    "cos": "math.cos",
    "tan": "math.tan",
    "exp": "math.exp",
    "log": "math.log",
    "ln": "math.log",
    "sqrt": "math.sqrt",
    "abs": "abs",
    # A network's activation, and a normal distribution's cumulative curve: the player's
    # own math has each of these, as Python's does.
    "tanh": "math.tanh",
    "sinh": "math.sinh",
    "cosh": "math.cosh",
    "atan": "math.atan",
    "erf": "math.erf",
    "log10": "math.log10",
    "log2": "math.log2",
}
_CONSTANTS = {"pi": "math.pi", "e": "math.e"}
_TOKEN = re.compile(
    r"\s*(?:(?P<number>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)|(?P<name>[A-Za-z][A-Za-z0-9]*)"
    r"|(?P<op>\*\*|<=|>=|&&|\|\||[-+*/^(),<>?:]))"
)
#: Words that join conditions, never values.
_LOGIC = {"and": "and", "or": "or", "&&": "and", "||": "or"}
_COMPARE: dict[type[ast.cmpop], str] = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}


def _conditional(tokens: list[str], text: str) -> list[str]:
    """``a ? b : c``, as a model may write it from C or JavaScript, written as Python writes
    it (``b if a else c``): within each bracket first, then at the top, from the right."""
    unread = FigureError([f"the formula {text[:40]!r} could not be read"])
    out: list[str] = []
    index = 0
    while index < len(tokens):
        if tokens[index] != "(":
            out.append(tokens[index])
            index += 1
            continue
        depth = 0
        for end in range(index, len(tokens)):
            depth += {"(": 1, ")": -1}.get(tokens[end], 0)
            if depth == 0:
                break
        if depth != 0:
            raise unread
        out += ["(", *_conditional(tokens[index + 1 : end], text), ")"]
        index = end + 1
    depth, asked, waiting = 0, None, 0
    for position, piece in enumerate(out):
        depth += {"(": 1, ")": -1}.get(piece, 0)
        if depth or piece not in ("?", ":"):
            continue
        if piece == "?":
            if asked is None:
                asked = position
            else:
                waiting += 1
        elif asked is None:
            raise unread
        elif waiting:
            waiting -= 1
        else:
            test, then = out[:asked], _conditional(out[asked + 1 : position], text)
            otherwise = _conditional(out[position + 1 :], text)
            if not test or not then or not otherwise:
                raise unread
            return ["(", "(", *then, ")", "if", "(", *test, ")", "else", "(", *otherwise, ")", ")"]
    if asked is not None:
        raise unread
    return out


def _python_expression(text: str, parameter: str | None) -> str:
    """A formula in ``x`` (and the slider's name) as Python over ``math``, or FigureError.

    Numbers, ``x``, the slider's name, pi and e, + - * / and powers (``^`` or ``**``),
    brackets, and sin, cos, tan, exp, log (or ln), sqrt and abs of one argument; and a
    comparison (< <= > >=, joined by and/&& or or/||), which is 1 where it holds and 0 where
    it does not, so that a piece of a curve is written "(x >= 0) * exp(-x)", or a choice
    between two values by one ("x >= 0 ? exp(-x) : 0"). Nothing else: no names, no
    attributes, no calls but those. "2x" is read as "2*x"."""
    tokens: list[tuple[str, str]] = []
    position = 0
    stripped = text.strip()
    while position < len(stripped):
        found = _TOKEN.match(stripped, position)
        if found is None or found.end() == position:
            raise FigureError([f"the formula {text[:40]!r} has something that is not arithmetic"])
        kind = found.lastgroup or ""
        tokens.append((kind, found.group(kind)))
        position = found.end()
    if not tokens or len(tokens) > 80:
        raise FigureError([f"the formula {text[:40]!r} is empty or too long"])

    variables = {"x"} | ({parameter} if parameter else set())
    joined: list[str] = []
    previous: tuple[str, str] | None = None
    for kind, value in tokens:
        # "2x", "x(x+1)", "(x+1)(x-1)", "2pi": a product written without its sign.
        if previous is not None:
            before_kind, before = previous
            ends_value = (
                before_kind == "number"
                or before == ")"
                or (before_kind == "name" and before not in _FUNCTIONS and before not in _LOGIC)
            )
            starts_value = (
                kind == "number" or (kind == "name" and value not in _LOGIC) or value == "("
            )
            if ends_value and starts_value:
                joined.append("*")
        joined.append("**" if value == "^" else _LOGIC.get(value, value))
        previous = (kind, value)
    joined = _conditional(joined, text)
    try:
        tree = ast.parse(" ".join(joined), mode="eval")
    except SyntaxError as error:
        raise FigureError([f"the formula {text[:40]!r} could not be read"]) from error
    if sum(1 for _ in ast.walk(tree)) > 120:
        raise FigureError([f"the formula {text[:40]!r} is too long"])

    def condition(node: ast.AST) -> str:
        if isinstance(node, ast.Compare):
            parts = []
            left = node.left
            for operator, right in zip(node.ops, node.comparators, strict=True):
                sign = _COMPARE.get(type(operator))
                if sign is None:
                    raise FigureError([f"the formula {text[:40]!r} compares in a way it cannot"])
                parts.append(f"({emit(left)} {sign} {emit(right)})")
                left = right
            return " and ".join(parts)
        if isinstance(node, ast.BoolOp):
            word = " and " if isinstance(node.op, ast.And) else " or "
            return "(" + word.join(f"({condition(value)})" for value in node.values) + ")"
        return f"({emit(node)} != 0)"

    def emit(node: ast.AST) -> str:
        if isinstance(node, ast.Expression):
            return emit(node.body)
        if isinstance(node, ast.Compare | ast.BoolOp):
            return f"(1.0 if {condition(node)} else 0.0)"
        if isinstance(node, ast.IfExp):
            return f"({emit(node.body)} if {condition(node.test)} else {emit(node.orelse)})"
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int | float)
            and not isinstance(node.value, bool)
        ):
            return _py(float(node.value))
        if isinstance(node, ast.Name):
            if node.id in variables:
                return "x" if node.id == "x" else "p"
            if node.id in _CONSTANTS:
                return _CONSTANTS[node.id]
            raise FigureError([f"the formula {text[:40]!r} names {node.id!r}"])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
            sign = "-" if isinstance(node.op, ast.USub) else "+"
            return f"({sign}{emit(node.operand)})"
        if isinstance(node, ast.BinOp):
            left, right = emit(node.left), emit(node.right)
            if isinstance(node.op, ast.Pow):
                return f"math.pow({left}, {right})"
            signs = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}
            for operator, sign in signs.items():
                if isinstance(node.op, operator):
                    return f"({left} {sign} {right})"
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCTIONS
            and len(node.args) == 1
            and not node.keywords
        ):
            return f"{_FUNCTIONS[node.func.id]}({emit(node.args[0])})"
        raise FigureError([f"the formula {text[:40]!r} has something that is not arithmetic"])

    return emit(tree)


def _function(source: str) -> Callable[[float, float], float]:
    """The formula as a function here, to try it before it is drawn."""
    code = compile(source, "<figure>", "eval")

    def value(x: float, p: float) -> float:
        result = eval(code, {"__builtins__": {}, "math": math, "abs": abs}, {"x": x, "p": p})  # noqa: S307 - only what _python_expression wrote
        return float(result)

    return value


def _samples(start: float, end: float, count: int = 161) -> list[float]:
    return [start + (end - start) * index / (count - 1) for index in range(count)]


def _runs_off(
    fn: Callable[[float, float], float],
    p: float,
    left: float,
    right: float,
    ends: tuple[float, float],
) -> bool:
    """Whether the curve runs off between two of its samples, as 1/x does across 0, rather
    than stepping from one value to the other, as a comparison does, or climbing steeply."""
    low, high = min(ends), max(ends)
    margin = high - low
    for step in range(1, 17):
        x = left + (right - left) * step / 17
        try:
            y = fn(x, p)
        except (ValueError, ZeroDivisionError, OverflowError):
            return True
        if not math.isfinite(y) or y < low - margin or y > high + margin:
            return True
    return False


def _tried(fn: Callable[[float, float], float], xs: list[float], ps: list[float]) -> list[float]:
    """The curve's values where it is drawn, or FigureError where it has none: a formula
    that cannot be worked out there, or one that runs off there, as 1/x does across 0. A
    step, where a comparison changes, is drawn as one: a cumulative curve is made of them."""
    values: list[float] = []
    for p in ps:
        row: list[float] = []
        for x in xs:
            try:
                y = fn(x, p)
            except (ValueError, ZeroDivisionError, OverflowError) as error:
                raise FigureError(["a curve has no value somewhere it is drawn"]) from error
            if not math.isfinite(y) or abs(y) > 1e6:
                raise FigureError(["a curve has no value somewhere it is drawn"])
            row.append(y)
        ordered = sorted(row)
        # How far the curve ranges, leaving out its most extreme tenth at each end.
        spread = ordered[len(ordered) * 9 // 10] - ordered[len(ordered) // 10]
        # A change between neighbours far larger than the curve's own range is looked at
        # closely: a pole is refused, a step or a steep climb is not. (A curve flat over
        # most of where it is drawn has no range but its steps.)
        limit = max(10 * max(spread, 1e-9), 1e-6)
        for index, (before, after) in enumerate(itertools.pairwise(row)):
            if abs(after - before) > limit and _runs_off(
                fn, p, xs[index], xs[index + 1], (before, after)
            ):
                raise FigureError(["a curve has no value somewhere it is drawn"])
        values += row
    return values


def _nice_step(span: float, ticks: int = 5) -> float:
    raw = span / max(1, ticks)
    power = float(10.0 ** math.floor(math.log10(raw)))
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * power:
            return factor * power
    return 10 * power


def _range(low: float, high: float, ticks: int = 5) -> tuple[float, float, float]:
    """An axis from about ``low`` to ``high`` in round steps, with its step: of the round
    steps that give about ``ticks`` of them, the one that leaves the least of the axis
    empty (a curve up to 9 is drawn to 10, not to 15)."""
    if high - low < 1e-9:
        low, high = low - 1, high + 1
    best: tuple[float, float, float] | None = None
    for count in range(max(2, ticks - 2), ticks + 4):
        step = _nice_step(high - low, count)
        start = math.floor(low / step + 1e-9) * step
        end = math.ceil(high / step - 1e-9) * step
        if best is None or end - start < best[1] - best[0] - 1e-9:
            best = (start, end, step)
    assert best is not None
    return best


def _on_axis(start: float, end: float) -> float:
    """Where the other axis crosses this one: at zero, or at the end nearest zero."""
    return min(max(0.0, start), end)


def _label_width(tex: str, size: int = 34) -> float:
    """About how wide a formula is drawn at ``size``, in the stage's units."""
    return _visible(tex) * 0.27 * size / 48 if tex else 0.0


#: The eight ways a label can stand from what it names, as the scene writes them.
_COMPASS = [
    "RIGHT",
    "UP + RIGHT",
    "UP",
    "UP + LEFT",
    "LEFT",
    "DOWN + LEFT",
    "DOWN",
    "DOWN + RIGHT",
]


def _compass(dx: float, dy: float) -> str:
    """The one of eight directions nearest to ``(dx, dy)``."""
    angle = math.atan2(dy, dx)
    return _COMPASS[round(angle / (math.pi / 4)) % 8]


def _tick_text(value: float) -> str:
    text = f"{value:.4g}"
    return text if "e" not in text else f"{value:.2f}"


def _tick_pairs(start: float, end: float, step: float, limit: int = 7) -> list[list[Any]]:
    return [[value, _tick_text(value)] for value in _ticks(start, end, step, limit)]


def _ticks(start: float, end: float, step: float, limit: int = 7) -> list[float]:
    """The ticks to put numbers to: every one, or, when there are more than ``limit``, the
    multiples of twice the step (then four times...), so that 0.5, 1.5, 2.5 never stand
    where 1, 2, 3 would."""
    count = round((end - start) / step)
    values = [start + step * index for index in range(count + 1)]
    spacing = step
    while len(values) > limit:
        spacing *= 2
        values = [value for value in values if abs(value / spacing - round(value / spacing)) < 1e-6]
    return [round(value, 6) for value in values]


def _legend_rows(labels: Sequence[str]) -> list[int]:
    """Which of two rows each name of a legend stands in: all in one when they fit."""
    shown = [index for index, label in enumerate(labels) if label]
    widths = [0.7 + _label_width(labels[index]) for index in shown]
    if sum(widths) + 0.7 * max(0, len(shown) - 1) <= 2 * _SAFE_X - 0.4:
        return [0] * len(labels)
    first = set(shown[: math.ceil(len(shown) / 2)])
    return [0 if index in first or not labels[index] else 1 for index in range(len(labels))]


def _point_side(
    fn: Callable[[float, float], float], x: float, start: float, end: float, steepness: float
) -> int:
    """Where a point's name stands clear of its curve, as an index into the scene's
    ``[UP + LEFT, UP + RIGHT, UP, DOWN]``: behind a rising curve and ahead of a falling one,
    both above it, and under a lowest point or over a highest. ``steepness`` turns a slope
    in the graph's numbers into one on the stage."""
    near = (end - start) / 400
    wide = (end - start) / 20
    try:
        left, right = max(start, x - near), min(end, x + near)
        slope = (fn(right, 0.0) - fn(left, 0.0)) / (right - left) * steepness
        before, after = max(start, x - wide), min(end, x + wide)
        middle = fn(x, 0.0)
        bend = (fn(before, 0.0) - middle) + (fn(after, 0.0) - middle)
    except (ArithmeticError, ValueError):
        return 2
    if slope > 0.35:
        return 0
    if slope < -0.35:
        return 1
    return 3 if bend > 1e-9 * (1 + abs(middle)) else 2


def _graph(figure: GraphFigure, beats: list[float]) -> tuple[str, bool]:
    x0, x1 = sorted(figure.x)
    if x1 - x0 < 1e-6:
        raise FigureError(["the x axis has no length"])
    slider = figure.slider
    trace = figure.trace
    if slider is not None and slider.name == "x":
        # A slider that moves x is a point that runs along the curve.
        slider, trace = None, True
    if slider is not None:
        low, high = sorted((slider.min, slider.max))
        if high - low < 1e-9 or not low <= slider.value <= high:
            raise FigureError(["the slider's value is not between its ends"])
        parameter_values = [low, (low + high) / 2, slider.value, high]
    else:
        parameter_values = [0.0]
    name = slider.name if slider is not None else None

    curves: list[tuple[str, float, float, str | None]] = []
    all_values: list[float] = []
    for curve in figure.curves:
        source = _python_expression(curve.f, name)
        start = x0 if curve.start is None else max(x0, curve.start)
        end = x1 if curve.end is None else min(x1, curve.end)
        if end - start < 1e-6:
            raise FigureError(["a curve is drawn over nothing"])
        all_values += _tried(_function(source), _samples(start, end), parameter_values)
        curves.append((source, start, end, curve.label))

    if figure.y is not None:
        y_low, y_high = sorted(figure.y)
    else:
        y_low, y_high = min(all_values), max(all_values)
        if y_low > 0 and y_low < 0.4 * y_high:
            y_low = 0.0
        if y_high < 0 and y_high > 0.4 * y_low:
            y_high = 0.0
        span = (y_high - y_low) or 1.0
        y_low -= 0.0 if y_low == 0 else 0.06 * span
        y_high += 0.1 * span
    if x0 > 0 and x0 < 0.4 * x1:
        x0 = 0.0
    x_start, x_end, x_step = _range(x0, x1, 6)
    y_start, y_end, y_step = _range(y_low, y_high, 4)
    axis_x = _on_axis(x_start, x_end)
    axis_y = _on_axis(y_start, y_end)

    # Curves are counted from 1; a model that counts from 0 numbers one of them 0. A curve
    # not named at all is the first.
    shade = figure.shade
    named = [
        item
        for item in [shade, *figure.rise, *figure.points]
        if item and "curve" in item.model_fields_set
    ]
    first = 0 if any(item.curve == 0 for item in named) else 1

    def curve_of(item: Shade | Rise | GraphPoint) -> int:
        return item.curve - first if "curve" in item.model_fields_set else 0

    def bound(value: float | str) -> float | None:
        """An end of the shaded area: a number, or None where it is the slider's value."""
        if isinstance(value, str):
            with contextlib.suppress(ValueError):
                return float(value)
            if slider is not None and value.strip() == slider.name:
                return None
            raise FigureError(["the shaded area ends at a name that is not the slider's"])
        return float(value)

    if shade is not None:
        index = curve_of(shade)
        if not 0 <= index < len(curves):
            raise FigureError(["the shaded area names a curve there is not"])
        source, start, end, _ = curves[index]
        ends = [bound(shade.start), bound(shade.end)]
        if ends[0] is None and ends[1] is None:
            raise FigureError(["the shaded area has no end that stays put"])
        if ends[0] is not None and ends[1] is not None:
            low, high = sorted((ends[0], ends[1]))
            low, high = max(low, start), min(high, end)
            if high - low < 1e-6:
                raise FigureError(["the shaded area is outside its curve"])
            ends = [low, high]
        else:
            # One end follows the slider; the other stays on the curve.
            ends = [None if item is None else min(max(item, start), end) for item in ends]
        shade_spec: list[Any] | None = [index, ends[0], ends[1], shade.label or "", start, end]
    else:
        shade_spec = None
    rise_specs: list[list[Any]] = []
    for rise in figure.rise:
        index = curve_of(rise)
        if not 0 <= index < len(curves):
            raise FigureError(["the rise names a curve there is not"])
        _, start, end, _ = curves[index]
        low, high = sorted((rise.start, rise.end))
        if high - low < 1e-6 or low < start - 1e-9 or high > end + 1e-9:
            raise FigureError(["the rise is not between two places on its curve"])
        rise_specs.append([index, low, high, rise.label or ""])
    interactive = slider is not None
    x_label = figure.x_label or ""
    # The name of the x axis stands to the right of its end, clear of anything drawn on it.
    x_length = round(min(10.0, 2 * (_SAFE_X - 0.3 - _label_width(x_label))), 2)
    # Every name in the legend, the shaded area's last: a row above the graph, or two.
    legend = [label or "" for _, _, _, label in curves]
    if len(legend) == 1 and legend[0] == (figure.y_label or ""):
        # One curve, named already by its axis.
        legend = [""]
    # A formula with a comparison in it is a curve in pieces (``_python_expression``).
    pieces = [" if " in source for source, _, _, _ in curves]
    if shade_spec is not None:
        legend.append(shade_spec[3])
    legend_rows = _legend_rows(legend)
    two_rows = 1 in legend_rows
    y_length = (4.2 if interactive else 4.9) - (0.5 if two_rows else 0.0)
    centre_y = (0.55 if interactive else -0.15) - (0.25 if two_rows else 0.0)
    legend_y = round(_SAFE_Y - 0.15, 2)

    points: list[list[Any]] = []
    for point in figure.points:
        index = curve_of(point)
        if not 0 <= index < len(curves):
            raise FigureError(["a point names a curve there is not"])
        source, start, end, _ = curves[index]
        if not start <= point.x <= end:
            raise FigureError(["a point is off its curve"])
        steepness = (y_length / (y_end - y_start)) / (x_length / (x_end - x_start))
        side = _point_side(_function(source), point.x, start, end, steepness)
        points.append([index, point.x, point.label or "", side])

    functions = "\n".join(
        f"    def curve_{index}(self, x, p):\n        return {source}\n"
        for index, (source, _, _, _) in enumerate(curves)
    )
    common = f"""\
{functions}
    def value(self, index, x, p):
        if index == 0:
            return self.curve_0(x, p)
        if index == 1:
            return self.curve_1(x, p)
        return self.curve_2(x, p)

    def build(self):
        axes = Axes(
            x_range={_py([x_start, x_end, x_step])},
            y_range={_py([y_start, y_end, y_step])},
            x_length={x_length},
            y_length={y_length},
            axis_config={{"color": self.muted, "include_tip": False}},
        ).move_to([0, {centre_y}, 0])
        numbers = VGroup()
        for tick in {_py(_tick_pairs(x_start, x_end, x_step))}:
            numbers.add(
                MathTex(tick[1], font_size=32, color=self.muted).next_to(
                    axes.c2p(tick[0], {_py(y_start)}), DOWN, buff=0.18
                )
            )
        for tick in {_py(_tick_pairs(y_start, y_end, y_step, 5))}:
            if tick[0] != {_py(y_start)}:
                numbers.add(
                    MathTex(tick[1], font_size=32, color=self.muted).next_to(
                        axes.c2p({_py(x_start)}, tick[0]), LEFT, buff=0.18
                    )
                )
        names = VGroup()
        x_label = {_py(x_label)}
        y_label = {_py(figure.y_label or "")}
        if x_label:
            names.add(
                MathTex(x_label, font_size=34, color=self.ink).next_to(
                    axes.c2p({_py(x_end)}, {_py(axis_y)}), RIGHT, buff=0.25
                )
            )
        if y_label:
            names.add(
                MathTex(y_label, font_size=34, color=self.ink).next_to(
                    axes.c2p({_py(axis_x)}, {_py(y_end)}), RIGHT, buff=0.25
                )
            )
        return axes, numbers, names

    def plot(self, axes, index, p, start, end):
        hues = [self.blue, self.green, self.violet]
        if {_py(pieces)}[index]:
            # A curve in pieces is drawn in short straight steps: smoothed, it would ripple
            # where it jumps.
            return axes.plot(
                lambda x: self.value(index, x, p),
                x_range=[start, end, (end - start) / 400],
                color=hues[index],
                use_smoothing=False,
            )
        return axes.plot(
            lambda x: self.value(index, x, p),
            x_range=[start, end],
            color=hues[index],
        )

    def rise(self, axes, spec, p, number):
        # How much the curve rises from one place to the other: a dashed run along, and
        # an arrow up by the difference, named beside it. Each rise has a hue of its own.
        hue = [self.coral, self.violet, self.green][number]
        below = self.value(spec[0], spec[1], p)
        above = self.value(spec[0], spec[2], p)
        start = axes.c2p(spec[1], below)
        corner = axes.c2p(spec[2], below)
        end = axes.c2p(spec[2], above)
        drawn = VGroup(
            DashedLine(start, corner, color=self.muted),
            Dot(color=hue, radius=0.08).move_to(start),
            Dot(color=hue, radius=0.08).move_to(end),
        )
        if abs(end[1] - corner[1]) > 0.05:
            arrow = DoubleArrow(corner, end, buff=0, color=hue, max_tip_length_to_length_ratio=0.25, max_stroke_width_to_length_ratio=12)
            drawn.add(arrow)
            if spec[3]:
                drawn.add(MathTex(spec[3], font_size=34, color=self.ink).next_to(arrow, RIGHT, buff=0.15))
        return drawn

    def area(self, axes, index, p, low, high):
        points = [axes.c2p(low, 0)]
        for step in range(61):
            x = low + (high - low) * step / 60
            points.append(axes.c2p(x, self.value(index, x, p)))
        points.append(axes.c2p(high, 0))
        return Polygon(*points, color=self.sun, fill_opacity=0.4, stroke_width=0)

    def legend(self):
        hues = [self.blue, self.green, self.violet]
        labels = {_py(legend)}
        rows = {_py(legend_rows)}
        lines = [VGroup(), VGroup()]
        counts = [0, 0]
        items = []
        for index in range(len(labels)):
            if not labels[index]:
                items.append(None)
                continue
            if index < {len(curves)}:
                key = Line([0, 0, 0], [0.5, 0, 0], color=hues[index])
                key.set_stroke(width=6)
            else:
                key = Rectangle(width=0.5, height=0.3, color=self.sun, fill_opacity=0.4, stroke_width=0)
            text = MathTex(labels[index], font_size=34, color=self.ink).next_to(key, RIGHT, buff=0.2)
            item = VGroup(key, text)
            items.append(item)
            lines[rows[index]].add(item)
            counts[rows[index]] += 1
        for row in range(2):
            if counts[row] > 0:
                lines[row].arrange(RIGHT, buff=0.7)
                if lines[row].width > {2 * _SAFE_X}:
                    lines[row].scale({2 * _SAFE_X} / lines[row].width)
                lines[row].move_to([0, {legend_y} - 0.58 * row, 0])
        return items
"""
    curve_specs = _py([[start, end] for _, start, end, _ in curves])
    if interactive:
        assert slider is not None
        low, high = sorted((slider.min, slider.max))
        body = (
            common
            + f"""
    def blueprint(self):
        self.state = {{"explored": False}}
        axes, numbers, names = self.build()
        spans = {curve_specs}
        knob = Slider(
            start=[-3.2, -2.95, 0],
            end=[3.2, -2.95, 0],
            value_range=({_py(low)}, {_py(high)}),
            init_value={_py(slider.value)},
            color=self.green,
        )
        self.adle_controls = {{{_py(slider.name.lower())}: knob}}
        name = MathTex({_py(slider.label or slider.name)}, font_size=34, color=self.ink)
        name.next_to(knob, LEFT, buff=0.4)
        reading = DecimalNumber({_py(slider.value)}, num_decimal_places=2, font_size=34, color=self.ink)
        reading.next_to(knob, RIGHT, buff=0.4)
        held = {{"curves": [], "area": None, "rises": []}}
        shade = {_py(shade_spec)}
        rises = {_py(rise_specs)}

        def draw():
            p = knob.get_value()
            for old in held["curves"]:
                self.remove(old)
            held["curves"] = []
            if held["area"] is not None:
                self.remove(held["area"])
                held["area"] = None
            if shade:
                # An end that is None follows the slider.
                low = p if shade[1] is None else shade[1]
                high = p if shade[2] is None else shade[2]
                ends = [low, high] if low <= high else [high, low]
                ends[0] = ends[0] if ends[0] >= shade[4] else shade[4]
                ends[1] = ends[1] if ends[1] <= shade[5] else shade[5]
                if ends[1] - ends[0] > 0.001:
                    held["area"] = self.area(axes, shade[0], p, ends[0], ends[1])
                    self.add(held["area"])
            for index in range(len(spans)):
                curve = self.plot(axes, index, p, spans[index][0], spans[index][1])
                held["curves"].append(curve)
                self.add(curve)
            for old in held["rises"]:
                self.remove(old)
            held["rises"] = []
            for number in range(len(rises)):
                drawn = self.rise(axes, rises[number], p, number)
                held["rises"].append(drawn)
                self.add(drawn)
            reading.set_value(p)

        def moved(control, previous, value):
            draw()
            if not self.state["explored"]:
                self.state["explored"] = True
                self.post_message("explored", True)

        knob.on_input(moved)
        self.add(axes, numbers, names, knob, name, reading)
        for item in self.legend():
            if item is not None:
                self.add(item)
        draw()
"""
        )
        return _scene(
            "GraphFigure", "A graph the learner changes with a slider.", body, interactive=True
        ), True

    steps = (
        1
        + len(curves)
        + (1 if shade_spec else 0)
        + len(rise_specs)
        + (1 if points else 0)
        + (1 if trace else 0)
    )
    holds = _paced(steps, beats, 1.2)
    body = (
        common
        + f"""
    def construct(self):
        holds = {_py(holds)}
        axes, numbers, names = self.build()
        spans = {curve_specs}
        self.play(Create(axes), FadeIn(numbers), FadeIn(names), run_time=1.2)
        self.wait(holds[0])
        step = 1
        legend = self.legend()
        drawn = []
        for index in range(len(spans)):
            curve = self.plot(axes, index, 0, spans[index][0], spans[index][1])
            drawn.append(curve)
            if legend[index] is not None:
                self.play(Create(curve), FadeIn(legend[index]), run_time=1.2)
            else:
                self.play(Create(curve), run_time=1.2)
            self.wait(holds[step])
            step += 1
        shade = {_py(shade_spec)}
        if shade:
            area = self.area(axes, shade[0], 0, shade[1], shade[2])
            parts = [FadeIn(area)]
            if legend[len(spans)] is not None:
                parts.append(FadeIn(legend[len(spans)]))
            self.play(*parts, run_time=1.2)
            self.wait(holds[step])
            step += 1
        rises = {_py(rise_specs)}
        for number in range(len(rises)):
            self.play(FadeIn(self.rise(axes, rises[number], 0, number)), run_time=1.2)
            self.wait(holds[step])
            step += 1
        marks = {_py(points)}
        if marks:
            sides = [UP + LEFT, UP + RIGHT, UP, DOWN]
            dots = VGroup()
            for mark in marks:
                place = axes.c2p(mark[1], self.value(mark[0], mark[1], 0))
                dot = Dot(color=self.coral, radius=0.1).move_to(place)
                dots.add(dot)
                if mark[2]:
                    dots.add(MathTex(mark[2], font_size=34, color=self.ink).next_to(dot, sides[mark[3]], buff=0.15))
            self.play(LaggedStart(*[GrowFromCenter(item) for item in dots], lag_ratio=0.25), run_time=1.2)
            self.wait(holds[step])
            step += 1
        if {_py(trace)}:
            where = ValueTracker(spans[0][0])
            runner = always_redraw(
                lambda: Dot(color=self.coral, radius=0.12).move_to(
                    axes.c2p(where.get_value(), self.value(0, where.get_value(), 0))
                )
            )
            self.add(runner)
            self.play(where.animate.set_value(spans[0][1]), run_time=2.4, rate_func=smooth)
            self.wait(holds[step])
"""
    )
    return _scene("GraphFigure", "A graph drawn one part at a time.", body), False


# -- bars --------------------------------------------------------------------------------------


def _bars(figure: BarsFigure, beats: list[float]) -> tuple[str, bool]:
    count = len(figure.labels)
    if len(figure.values) != count or (figure.then is not None and len(figure.then) != count):
        raise FigureError(["the bars have a different number of labels and values"])
    if figure.highlight is not None and figure.highlight > count:
        raise FigureError(["the bar to point at is not there"])
    every = figure.values + (figure.then or [])
    top = max(max(every), 0.0)
    bottom = min(min(every), 0.0)
    span = (top - bottom) or 1.0
    height = 4.2
    base_y = round(-2.3 + height * (-bottom / span), 3)
    width = round(min(1.4, 9.6 / count * 0.6), 3)
    gap = round(min(11.2 / count, 2.4), 3)
    xs = [round((index - (count - 1) / 2) * gap, 3) for index in range(count)]

    def tall(values: list[float]) -> list[float]:
        return [round(value / span * height, 4) for value in values]

    def shown(values: list[float]) -> list[str]:
        return [f"{value:.3g}" for value in values]

    steps = 2 + (1 if figure.highlight else 0) + (1 if figure.then else 0)
    holds = _paced(steps, beats, 1.2)
    body = f"""\
    def bar(self, x, height, hue):
        bar = Rectangle(width={width}, height=max(0.02, abs(height)), color=hue, fill_opacity=0.6)
        bar.move_to([x, {base_y} + height / 2, 0])
        return bar

    def construct(self):
        holds = {_py(holds)}
        xs = {_py(xs)}
        heights = {_py(tall(figure.values))}
        values = {_py(shown(figure.values))}
        names = {_py(figure.labels)}
        baseline = Line([-6.0, {base_y}, 0], [6.0, {base_y}, 0], color=self.muted)
        labels = VGroup()
        for index in range(len(xs)):
            labels.add(
                Text(names[index], font_size=24, color=self.muted).move_to(
                    [xs[index], {base_y} - 0.45 if heights[index] >= 0 else {base_y} + 0.45, 0]
                )
            )
        unit = {_py(figure.y_label or "")}
        extra = []
        if unit:
            extra.append(FadeIn(MathTex(unit, font_size=34, color=self.ink).to_edge(UP, buff=0.4)))
        self.play(Create(baseline), FadeIn(labels), *extra, run_time=1.2)
        self.wait(holds[0])
        bars = VGroup()
        numbers = VGroup()
        for index in range(len(xs)):
            hue = self.blue if heights[index] >= 0 else self.coral
            bar = self.bar(xs[index], heights[index], hue)
            bars.add(bar)
            numbers.add(
                Text(values[index], font_size=24, color=self.ink).next_to(
                    bar, UP if heights[index] >= 0 else DOWN, buff=0.15
                )
            )
        self.play(
            LaggedStart(*[FadeIn(bar, shift=UP * 0.4) for bar in bars], lag_ratio=0.15),
            FadeIn(numbers),
            run_time=1.4,
        )
        self.wait(holds[1])
        step = 2
        pick = {_py((figure.highlight or 0) - 1)}
        if pick >= 0:
            self.play(Indicate(bars[pick]), Indicate(numbers[pick]), run_time=1.2)
            self.wait(holds[step])
            step += 1
        later = {_py(tall(figure.then) if figure.then else [])}
        if later:
            shown = {_py(shown(figure.then) if figure.then else [])}
            moves = []
            for index in range(len(xs)):
                hue = self.blue if later[index] >= 0 else self.coral
                bar = self.bar(xs[index], later[index], hue)
                number = Text(shown[index], font_size=24, color=self.ink).next_to(
                    bar, UP if later[index] >= 0 else DOWN, buff=0.15
                )
                moves.append(Transform(bars[index], bar))
                moves.append(Transform(numbers[index], number))
            self.play(*moves, run_time=1.4)
            self.wait(holds[step])
"""
    return _scene("BarsFigure", "Bars drawn and then changed.", body), False


# -- number line -------------------------------------------------------------------------------


def _number_line(figure: NumberLineFigure, beats: list[float]) -> tuple[str, bool]:
    low, high = sorted((figure.start, figure.end))
    if high - low < 1e-6:
        raise FigureError(["the number line has no length"])
    start, end, step = _range(low, high, 6)

    def place(value: float) -> float:
        return round(-5.8 + 11.6 * (value - start) / (end - start), 3)

    for value in [mark.at for mark in figure.marks] + [
        bound
        for span in (figure.interval, figure.move)
        if span is not None
        for bound in (span.start, span.end)
    ]:
        if not start - 1e-9 <= value <= end + 1e-9:
            raise FigureError(["a mark is off the number line"])
    ticks = [[place(value), _tick_text(value)] for value in _ticks(start, end, step, 9)]
    marks = [[place(mark.at), mark.label or ""] for mark in figure.marks]
    interval = (
        [place(figure.interval.start), place(figure.interval.end), figure.interval.label or ""]
        if figure.interval
        else []
    )
    move = (
        [place(figure.move.start), place(figure.move.end), figure.move.label or ""]
        if figure.move
        else []
    )
    steps = 1 + (1 if marks else 0) + (1 if interval else 0) + (1 if move else 0)
    holds = _paced(steps, beats, 1.2)
    body = f"""\
    def construct(self):
        holds = {_py(holds)}
        line = Line([-6.0, -0.4, 0], [6.0, -0.4, 0], color=self.muted)
        ticks = VGroup()
        for tick in {_py(ticks)}:
            ticks.add(Line([tick[0], -0.55, 0], [tick[0], -0.25, 0], color=self.muted))
            ticks.add(MathTex(tick[1], font_size=32, color=self.muted).move_to([tick[0], -1.0, 0]))
        self.play(Create(line), FadeIn(ticks), run_time=1.2)
        self.wait(holds[0])
        step = 1
        marks = {_py(marks)}
        if marks:
            dots = VGroup()
            for mark in marks:
                # Over the interval drawn later, which would hide half of it.
                dot = Dot(color=self.coral, radius=0.11).move_to([mark[0], -0.4, 0]).set_z_index(2)
                dots.add(dot)
                if mark[1]:
                    dots.add(MathTex(mark[1], font_size=34, color=self.ink).next_to(dot, UP, buff=0.3))
            self.play(LaggedStart(*[FadeIn(item, shift=DOWN * 0.2) for item in dots], lag_ratio=0.2), run_time=1.2)
            self.wait(holds[step])
            step += 1
        interval = {_py(interval)}
        if interval:
            band = Line([interval[0], -0.4, 0], [interval[1], -0.4, 0], color=self.green)
            band.set_stroke(width=12)
            parts = [Create(band)]
            if interval[2]:
                words = MathTex(interval[2], font_size=34, color=self.ink)
                words.move_to([(interval[0] + interval[1]) / 2, 0.75, 0])
                parts.append(Write(words))
            self.play(*parts, run_time=1.2)
            self.wait(holds[step])
            step += 1
        move = {_py(move)}
        if move:
            where = ValueTracker(move[0])
            runner = always_redraw(lambda: Dot(color=self.blue, radius=0.14).move_to([where.get_value(), -0.4, 0]).set_z_index(3))
            self.add(runner)
            self.play(where.animate.set_value(move[1]), run_time=2.0, rate_func=smooth)
            self.wait(holds[step])
"""
    return _scene("NumberLineFigure", "A number line with marks and a moving point.", body), False


# -- flow --------------------------------------------------------------------------------------


def _wrapped(text: str, width: int = 14) -> list[str]:
    """A step's words in one line or two, each drawn centered in its box."""
    words = text.split()
    lines: list[str] = []
    for word in words:
        if lines and len(lines[-1]) + 1 + len(word) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines if len(lines) <= 2 else [lines[0], " ".join(lines[1:])]


def _flow(figure: FlowFigure, beats: list[float]) -> tuple[str, bool]:
    count = len(figure.steps)
    per_row = count if count <= 3 else math.ceil(count / 2)
    rows = 1 if count <= 3 else 2
    gap = round(11.0 / per_row, 3)
    places: list[list[float]] = []
    for index in range(count):
        row, column = divmod(index, per_row)
        # The second row runs back the other way, so that each arrow is short.
        if row == 1:
            column = per_row - 1 - column
        x = round((column - (per_row - 1) / 2) * gap, 3)
        y = 0.9 if rows == 2 and row == 0 else (-1.3 if rows == 2 else 0.0)
        places.append([x, y])
    labels = [_wrapped(step) for step in figure.steps]
    loop = figure.loop and rows == 1
    holds = _paced(count + (1 if loop else 0), beats, 1.0)
    body = f"""\
    def construct(self):
        holds = {_py(holds)}
        places = {_py(places)}
        names = {_py(labels)}
        boxes = []
        for index in range(len(names)):
            text = VGroup(*[Text(line, font_size=26, color=self.ink) for line in names[index]])
            text.arrange(DOWN, buff=0.12)
            text.move_to([places[index][0], places[index][1], 0])
            frame = SurroundingRectangle(text, color=self.muted, buff=0.3)
            boxes.append(VGroup(frame, text))
        for index in range(len(boxes)):
            parts = [FadeIn(boxes[index], shift=RIGHT * 0.2)]
            if index > 0:
                before = boxes[index - 1][0]
                here = boxes[index][0]
                if abs(places[index][1] - places[index - 1][1]) > 0.1:
                    ends = [before.get_bottom(), here.get_top()]
                elif places[index][0] > places[index - 1][0]:
                    ends = [before.get_right(), here.get_left()]
                else:
                    ends = [before.get_left(), here.get_right()]
                # As thick, and with as large a head, however short the gap is.
                arrow = Arrow(ends[0], ends[1], buff=0.1, color=self.green, max_tip_length_to_length_ratio=0.45, max_stroke_width_to_length_ratio=12)
                parts.append(GrowArrow(arrow))
                self.play(boxes[index - 1][0].animate.set_stroke(color=self.muted), run_time=0.3)
            self.play(*parts, run_time=1.0)
            self.play(boxes[index][0].animate.set_stroke(color=self.green), run_time=0.3)
            self.wait(holds[index])
        if {_py(loop)}:
            first = boxes[0][0]
            last = boxes[len(boxes) - 1][0]
            # One level under both boxes, however tall each is.
            low = first.get_bottom()[1]
            if last.get_bottom()[1] < low:
                low = last.get_bottom()[1]
            low = low - 0.9
            corner = [last.get_bottom()[0], low, 0]
            turn = [first.get_bottom()[0], low, 0]
            path = VGroup(
                Line(last.get_bottom(), corner, color=self.green),
                Line(corner, turn, color=self.green),
            )
            path.set_stroke(width=6)
            back = Arrow(turn, first.get_bottom(), buff=0.05, color=self.green, max_tip_length_to_length_ratio=0.45, max_stroke_width_to_length_ratio=12)
            self.play(Create(path), GrowArrow(back), run_time=1.2)
            self.wait(holds[len(holds) - 1])
"""
    return _scene("FlowFigure", "Steps that follow one another.", body), False


# -- layers ------------------------------------------------------------------------------------


def _layers(figure: LayersFigure, beats: list[float]) -> tuple[str, bool]:
    count = len(figure.layers)
    path = figure.path
    if path is not None and (
        len(path) != count
        or any(
            not 1 <= node <= layer.nodes for node, layer in zip(path, figure.layers, strict=True)
        )
    ):
        raise FigureError(["the path does not name one node in each layer"])
    xs = [round(-4.8 + 9.6 * index / (count - 1), 3) for index in range(count)]
    columns = []
    for x, layer in zip(xs, figure.layers, strict=True):
        spacing = min(0.95, 4.6 / max(1, layer.nodes - 1)) if layer.nodes > 1 else 0
        ys = [
            round((layer.nodes - 1) / 2 * spacing - index * spacing - 0.35, 3)
            for index in range(layer.nodes)
        ]
        columns.append([[x, y] for y in ys])
    labels = [layer.label for layer in figure.layers]
    route = [node - 1 for node in path] if path else []
    holds = _paced(count + (1 if route else 0), beats, 1.0)
    body = f"""\
    def construct(self):
        holds = {_py(holds)}
        columns = {_py(columns)}
        names = {_py(labels)}
        nodes = []
        for index in range(len(columns)):
            column = VGroup()
            for place in columns[index]:
                column.add(Circle(radius=0.26, color=self.blue, fill_opacity=0.2).move_to([place[0], place[1], 0]))
            nodes.append(column)
        for index in range(len(columns)):
            title = Text(names[index], font_size=24, color=self.muted).move_to([columns[index][0][0], 2.95, 0])
            parts = [LaggedStart(*[GrowFromCenter(node) for node in nodes[index]], lag_ratio=0.1), FadeIn(title)]
            if index > 0:
                links = VGroup()
                for left in nodes[index - 1]:
                    for right in nodes[index]:
                        link = Line(left.get_right(), right.get_left(), color=self.muted)
                        link.set_stroke(width=1.5, opacity=0.55)
                        links.add(link)
                parts.append(Create(links))
            self.play(*parts, run_time=1.0)
            self.wait(holds[index])
        route = {_py(route)}
        if route:
            lit = []
            for index in range(len(route)):
                node = nodes[index][route[index]]
                lit.append(node.animate.set_fill(self.green, 0.7))
            pulse = Dot(color=self.coral, radius=0.12).move_to(nodes[0][route[0]].get_center())
            self.play(*lit, FadeIn(pulse), run_time=0.8)
            for index in range(1, len(route)):
                self.play(pulse.animate.move_to(nodes[index][route[index]].get_center()), run_time=0.6)
            self.play(FadeOut(pulse), run_time=0.4)
            self.wait(holds[len(holds) - 1])
"""
    return _scene("LayersFigure", "Layers of nodes, joined, and a path through them.", body), False


# -- table -------------------------------------------------------------------------------------


#: Characters with a meaning in TeX, as they are written inside \\text{...}.
_IN_TEXT = {"%": r"\%", "#": r"\#", "&": r"\&", "_": r"\_", "\\": "", "{": "", "}": "",
            "^": "", "~": ""}  # fmt: skip


def _mixed(text: str) -> str:
    """Words with formulas among them ("If $x_1 < x_2$ then $F(x_1) \\le F(x_2)$") as one
    formula, the words set as text."""
    pieces = text.split("$")
    if len(pieces) % 2 == 0:
        raise ValueError("has a $ without its pair")
    parts = []
    for index, piece in enumerate(pieces):
        if index % 2:
            parts.append(piece)
        elif piece.strip():
            words = "".join(_IN_TEXT.get(char, char) for char in _plain(piece))
            # A space at either end of the words is kept: it stands between them and the
            # formula beside them.
            lead = " " if piece[:1] == " " else ""
            trail = " " if piece[-1:] == " " else ""
            parts.append(r"\text{" + lead + words + trail + "}")
    return _tex(" ".join(parts))


#: TeX written without its dollar signs: a command (``\frac``, ``\{``, ``\emptyset``), or a
#: letter with a subscript or a power (``E_1``, ``x^2``).
_BARE_TEX = re.compile(r"\\[A-Za-z]{2,}|\\[{}]|(?<![A-Za-z])[A-Za-z][_^](?:\{|[A-Za-z0-9])")


def _cell(text: str, *, heading: bool = False) -> list[Any]:
    """A cell as ``[is a formula, what is drawn]``: words, a formula (``$...$``), or words
    with formulas among them, set as one formula with the words as text (``_mixed``). A
    heading of a single letter names a variable and is set as the formulas under it are.

    TeX written without dollar signs is set as a formula too, its words as text: a real
    lesson's table showed ``\\{H, T\\}`` and ``\\emptyset`` as they were typed, backslashes
    and all (2026-11-22). Backslashes written twice in a cell, where a line cannot break,
    are read as one."""
    text = " ".join(text.split())
    if not text:
        return [False, " "]
    if "$" in text:
        return [True, _mixed(text)]
    if heading and re.fullmatch(r"[A-Za-z]", text):
        return [True, text]
    # So is mathematics written in its own symbols ("E ⊆ Ω"), which the text face lacks.
    if _BARE_TEX.search(text) or any(char in UNICODE_TEX for char in text):
        once = re.sub(r"\\{2,}", lambda run: "\\" * max(1, len(run.group(0)) // 2), text)
        with contextlib.suppress(ValueError):
            return [True, _tex(once)]
    return [False, _plain(text)]


def _cell_width(spec: list[Any]) -> float:
    """About how wide a cell is drawn: words at 26, formulas at 34."""
    if spec[0]:
        return _label_width(re.sub(r"\\text\{([^}]*)\}", lambda m: m.group(1), spec[1]))
    return len(spec[1]) * 0.27 * 26 / 48


def _table(figure: TableFigure, beats: list[float]) -> tuple[str, bool]:
    columns = len(figure.header)
    if any(len(row) != columns for row in figure.rows):
        raise FigureError(["a row of the table has a different number of cells"])
    if any(not 1 <= row <= len(figure.rows) for row in figure.highlight):
        raise FigureError(["the table has no such row to point at"])
    try:
        header = [_cell(cell, heading=True) for cell in figure.header]
        rows = [[_cell(cell) for cell in row] for row in figure.rows]
    except ValueError as error:
        raise FigureError([f"a cell of the table: {error}"]) from error
    # Each column as wide as its widest cell, the table no wider than the stage: a cell
    # still too wide for its column is drawn smaller to fit it.
    needed = [
        max(1.4, max(_cell_width(row[index]) for row in [header, *rows]) + 0.5)
        for index in range(columns)
    ]
    scale = min(1.0, 11.6 / sum(needed))
    widths = [round(item * scale, 3) for item in needed]
    left = -sum(widths) / 2
    xs = []
    for item in widths:
        xs.append(round(left + item / 2, 3))
        left += item
    count = len(rows) + 1
    height = round(min(0.85, 5.8 / count), 3)
    ys = [round(2.6 - index * height, 3) for index in range(count)]
    picks = list(figure.highlight)
    holds = _paced(2 + len(picks), beats, 1.0)
    body = f"""\
    def cell(self, spec, hue, room):
        if spec[0]:
            made = MathTex(spec[1], font_size=34, color=hue)
        else:
            made = Text(spec[1], font_size=26, color=hue)
        if made.width > room:
            made.scale(room / made.width)
        return made

    def construct(self):
        holds = {_py(holds)}
        xs = {_py(xs)}
        rooms = {_py([round(item - 0.3, 3) for item in widths])}
        ys = {_py(ys)}
        header = {_py(header)}
        rows = {_py(rows)}
        heading = VGroup()
        for index in range(len(header)):
            heading.add(self.cell(header[index], self.ink, rooms[index]).move_to([xs[index], ys[0], 0]))
        rule = Line([{_py(round(-sum(widths) / 2, 3))}, ys[0] - {height} / 2, 0], [{_py(round(sum(widths) / 2, 3))}, ys[0] - {height} / 2, 0], color=self.muted)
        self.play(FadeIn(heading), Create(rule), run_time=1.0)
        self.wait(holds[0])
        lines = []
        for row in range(len(rows)):
            line = VGroup()
            for index in range(len(header)):
                line.add(self.cell(rows[row][index], self.ink, rooms[index]).move_to([xs[index], ys[row + 1], 0]))
            lines.append(line)
        self.play(LaggedStart(*[FadeIn(line, shift=UP * 0.15) for line in lines], lag_ratio=0.2), run_time=1.2)
        self.wait(holds[1])
        picks = {_py(picks)}
        step = 2
        for pick in picks:
            frame = SurroundingRectangle(lines[pick - 1], color=self.sun, buff=0.12)
            self.play(Create(frame), run_time=0.7)
            self.wait(holds[step])
            self.play(FadeOut(frame), run_time=0.3)
            step += 1
"""
    return _scene("TableFigure", "A table filled in, one row after another.", body), False


# -- scatter -----------------------------------------------------------------------------------


def _scatter(figure: ScatterFigure, beats: list[float]) -> tuple[str, bool]:
    if any(len(point) != 2 for point in figure.points):
        raise FigureError(["a point of the scatter is not [x, y]"])
    xs = [point[0] for point in figure.points]
    ys = [point[1] for point in figure.points]
    line = figure.line
    if line is not None:
        ys_line = [line.slope * x + line.intercept for x in (min(xs), max(xs))]
        ys_all = ys + ys_line
    else:
        ys_all = ys
    x_start, x_end, x_step = _range(
        min(xs) - 0.05 * (max(xs) - min(xs) or 1), max(xs) + 0.05 * (max(xs) - min(xs) or 1), 6
    )
    y_low, y_high = min(ys_all), max(ys_all)
    pad = 0.08 * ((y_high - y_low) or 1)
    y_start, y_end, y_step = _range(y_low - pad, y_high + pad, 4)
    axis_x = _on_axis(x_start, x_end)
    axis_y = _on_axis(y_start, y_end)
    x_length = round(min(10.0, 2 * (_SAFE_X - 0.3 - _label_width(figure.x_label or ""))), 2)
    steps = 2 + (1 if line else 0) + (1 if line and figure.residuals else 0)
    holds = _paced(steps, beats, 1.2)
    # The line's name stands above it where it ends on the right, or, for a line that falls,
    # where it begins on the left: never across it.
    rising = line is None or line.slope >= 0
    fit = [line.slope, line.intercept, line.label or "", 0 if rising else 1] if line else []
    body = f"""\
    def construct(self):
        holds = {_py(holds)}
        axes = Axes(
            x_range={_py([x_start, x_end, x_step])},
            y_range={_py([y_start, y_end, y_step])},
            x_length={x_length},
            y_length=4.9,
            axis_config={{"color": self.muted, "include_tip": False}},
        ).move_to([0, -0.15, 0])
        numbers = VGroup()
        for tick in {_py(_tick_pairs(x_start, x_end, x_step))}:
            numbers.add(MathTex(tick[1], font_size=32, color=self.muted).next_to(axes.c2p(tick[0], {_py(y_start)}), DOWN, buff=0.18))
        for tick in {_py(_tick_pairs(y_start, y_end, y_step, 5))}:
            if tick[0] != {_py(y_start)}:
                numbers.add(MathTex(tick[1], font_size=32, color=self.muted).next_to(axes.c2p({_py(x_start)}, tick[0]), LEFT, buff=0.18))
        names = VGroup()
        if {_py(figure.x_label or "")}:
            names.add(MathTex({_py(figure.x_label or "")}, font_size=34, color=self.ink).next_to(axes.c2p({_py(x_end)}, {_py(axis_y)}), RIGHT, buff=0.25))
        if {_py(figure.y_label or "")}:
            names.add(MathTex({_py(figure.y_label or "")}, font_size=34, color=self.ink).next_to(axes.c2p({_py(axis_x)}, {_py(y_end)}), RIGHT, buff=0.25))
        self.play(Create(axes), FadeIn(numbers), FadeIn(names), run_time=1.2)
        self.wait(holds[0])
        points = {_py([[x, y] for x, y in zip(xs, ys, strict=True)])}
        dots = VGroup()
        for point in points:
            dots.add(Dot(color=self.blue, radius=0.08).move_to(axes.c2p(point[0], point[1])))
        self.play(LaggedStart(*[GrowFromCenter(dot) for dot in dots], lag_ratio=0.05), run_time=1.2)
        self.wait(holds[1])
        fit = {_py(fit)}
        if fit:
            low = {_py(min(xs))}
            high = {_py(max(xs))}
            trend = axes.plot(lambda x: fit[0] * x + fit[1], x_range=[low, high], color=self.green)
            parts = [Create(trend)]
            if fit[2]:
                words = MathTex(fit[2], font_size=34, color=self.ink)
                if fit[3] == 0:
                    words.next_to(axes.c2p(high, fit[0] * high + fit[1]), UP + LEFT, buff=0.2)
                else:
                    words.next_to(axes.c2p(low, fit[0] * low + fit[1]), UP + RIGHT, buff=0.2)
                parts.append(Write(words))
            self.play(*parts, run_time=1.2)
            self.wait(holds[2])
            if {_py(figure.residuals)}:
                gaps = VGroup()
                for point in points:
                    gaps.add(Line(axes.c2p(point[0], point[1]), axes.c2p(point[0], fit[0] * point[0] + fit[1]), color=self.coral))
                self.play(Create(gaps), run_time=1.2)
                self.wait(holds[3])
"""
    return _scene("ScatterFigure", "Points, and a line through them.", body), False


# -- vectors -----------------------------------------------------------------------------------


def _vectors(figure: VectorsFigure, beats: list[float]) -> tuple[str, bool]:
    given = [(vector.x, vector.y) for vector in figure.vectors]
    labels = [vector.label or "" for vector in figure.vectors]
    if any(math.hypot(x, y) < 1e-6 for x, y in given):
        raise FigureError(["a vector has no length"])
    adding = figure.sum and len(given) >= 2
    # Every point an arrow reaches: each vector's tip and, added one after another, each
    # running total.
    reached = list(given)
    total = (0.0, 0.0)
    for x, y in given:
        total = (total[0] + x, total[1] + y)
        if adding:
            reached.append(total)
    shows_total = adding and math.hypot(*total) > 1e-6
    # One scale across and up, or every angle would be drawn wrong.
    extent_x = max(max(abs(x) for x, _ in reached), 1.0) * 1.2
    extent_y = max(max(abs(y) for _, y in reached), 1.0) * 1.2
    step = _nice_step(2 * max(extent_x, extent_y), 8)
    half_y = math.ceil(extent_y / step - 1e-9) * step
    half_x = math.ceil(extent_x / step - 1e-9) * step
    widest, tallest = 12.0, 6.1
    half_x = max(half_x, math.floor(half_y * widest / tallest / step + 1e-9) * step)
    unit = min(tallest / (2 * half_y), widest / (2 * half_x))
    x_length, y_length = round(2 * half_x * unit, 3), round(2 * half_y * unit, 3)

    def away(index: int) -> int:
        """The side of a vector its name stands on: the one the other arrows are not on."""
        x, y = given[index]
        length = math.hypot(x, y)
        left = (-y / length, x / length)
        others = [given[other] for other in range(len(given)) if other != index]
        if shows_total:
            others.append(total)
        lean = sum((left[0] * ox + left[1] * oy) / math.hypot(ox, oy) for ox, oy in others)
        side = left if lean <= 1e-9 else (-left[0], -left[1])
        return _COMPASS.index(_compass(*side))

    specs = [[x, y, labels[index], away(index)] for index, (x, y) in enumerate(given)]
    joined = " + ".join(labels)
    sum_label = joined if all(labels) and _visible(joined) <= 30 else ""
    total_spec = [total[0], total[1], sum_label, _COMPASS.index(_compass(*total))]
    holds = _paced(len(given) + (1 if adding else 0), beats, 1.0)
    body = f"""    def construct(self):
        holds = {_py(holds)}
        axes = Axes(
            x_range={_py([-half_x, half_x, step])},
            y_range={_py([-half_y, half_y, step])},
            x_length={x_length},
            y_length={y_length},
            axis_config={{"color": self.muted, "include_tip": False}},
        ).move_to([0, -0.2, 0])
        self.add(axes)
        sides = [{", ".join(_COMPASS)}]
        hues = [self.blue, self.green, self.violet]
        vectors = {_py(specs)}
        arrows = []
        for index in range(len(vectors)):
            vector = vectors[index]
            arrow = Arrow(axes.c2p(0, 0), axes.c2p(vector[0], vector[1]), buff=0, color=hues[index], max_tip_length_to_length_ratio=0.35, max_stroke_width_to_length_ratio=12)
            arrows.append(arrow)
            parts = [GrowArrow(arrow)]
            if vector[2]:
                name = MathTex(vector[2], font_size=36, color=self.ink)
                name.next_to(axes.c2p(vector[0] / 2, vector[1] / 2), sides[vector[3]], buff=0.15)
                parts.append(FadeIn(name))
            self.play(*parts, run_time=1.0)
            self.wait(holds[index])
        if {_py(adding)}:
            tip = [vectors[0][0], vectors[0][1]]
            moved = []
            for index in range(1, len(vectors)):
                vector = vectors[index]
                copy = Arrow(axes.c2p(tip[0], tip[1]), axes.c2p(tip[0] + vector[0], tip[1] + vector[1]), buff=0, color=hues[index], max_tip_length_to_length_ratio=0.35, max_stroke_width_to_length_ratio=12)
                moved.append(TransformFromCopy(arrows[index], copy))
                tip = [tip[0] + vector[0], tip[1] + vector[1]]
            self.play(*moved, run_time=1.2)
            total = {_py(total_spec)}
            if {_py(shows_total)}:
                result = Arrow(axes.c2p(0, 0), axes.c2p(total[0], total[1]), buff=0, color=self.coral, max_tip_length_to_length_ratio=0.35, max_stroke_width_to_length_ratio=12)
                parts = [GrowArrow(result)]
                if total[2]:
                    name = MathTex(total[2], font_size=36, color=self.ink)
                    name.next_to(axes.c2p(total[0], total[1]), sides[total[3]], buff=0.15)
                    parts.append(FadeIn(name))
                self.play(*parts, run_time=1.0)
            self.wait(holds[len(holds) - 1])
"""
    return _scene("VectorsFigure", "Vectors drawn from the origin, and their sum.", body), False


# -- tree --------------------------------------------------------------------------------------


def _branch_side(ys: dict[int, float], parents: list[int | None], index: int) -> int:
    """Where a branch's words stand: under a branch that falls and over one that rises,
    outside the fan of branches, where they cannot be read as another branch's."""
    parent = parents[index]
    return -1 if parent is not None and ys[index] < ys[parent] - 0.05 else 1


def _tree(figure: TreeFigure, beats: list[float]) -> tuple[str, bool]:
    nodes = figure.nodes
    if nodes[0].parent is not None:
        raise FigureError(["the first node of a tree is its root, without a parent"])
    parents: list[int | None] = [None]
    depths = [0]
    for index, node in enumerate(nodes[1:], start=1):
        if node.parent is None or not 1 <= node.parent <= index:
            raise FigureError(["each node after the first names an earlier node as its parent"])
        parents.append(node.parent - 1)
        depths.append(depths[node.parent - 1] + 1)
    deepest = max(depths)
    if deepest > 4:
        raise FigureError(["the tree is deeper than four levels"])
    children: dict[int, list[int]] = {}
    for index, parent in enumerate(parents):
        if parent is not None:
            children.setdefault(parent, []).append(index)
    leaves = [index for index in range(len(nodes)) if index not in children]
    ys: dict[int, float] = {}
    spacing = min(1.1, 6.0 / max(1, len(leaves) - 1)) if len(leaves) > 1 else 0
    for order, leaf in enumerate(leaves):
        ys[leaf] = round((len(leaves) - 1) / 2 * spacing - order * spacing - 0.2, 3)

    def place(index: int) -> float:
        if index not in ys:
            below = [place(child) for child in children[index]]
            ys[index] = round(sum(below) / len(below), 3)
        return ys[index]

    place(0)
    xs = [round(-5.4 + 10.8 * depth / max(1, deepest), 3) for depth in depths]
    specs = [
        [
            xs[index],
            ys[index],
            node.label,
            -1 if parents[index] is None else parents[index],
            node.edge or "",
            depths[index],
            _branch_side(ys, parents, index),
        ]
        for index, node in enumerate(nodes)
    ]
    holds = _paced(deepest + 1, beats, 1.0)
    body = f"""\
    def construct(self):
        holds = {_py(holds)}
        nodes = {_py(specs)}
        shown = []
        for spec in nodes:
            text = Text(spec[2], font_size=26, color=self.ink).move_to([spec[0], spec[1], 0])
            frame = SurroundingRectangle(text, color=self.blue, buff=0.16)
            shown.append(VGroup(frame, text))
        for depth in range({deepest + 1}):
            parts = []
            for index in range(len(nodes)):
                spec = nodes[index]
                if spec[5] != depth:
                    continue
                parts.append(FadeIn(shown[index], shift=RIGHT * 0.2))
                if spec[3] >= 0:
                    origin = shown[spec[3]]
                    branch = Line(origin.get_right(), shown[index].get_left(), color=self.muted)
                    parts.append(Create(branch))
                    if spec[4]:
                        label = MathTex(spec[4], font_size=34, color=self.ink)
                        label.move_to(branch.get_center() + UP * (0.32 * spec[6]))
                        parts.append(FadeIn(label))
            self.play(*parts, run_time=1.0)
            self.wait(holds[depth])
"""
    return _scene("TreeFigure", "A tree drawn one level at a time.", body), False
