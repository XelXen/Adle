"""Slides: the picture of a teaching part, as a script the model writes and the core draws.

ADR-049. A lesson is watched as one slideshow: each part that teaches has a picture, and
the picture changes as the narration goes. Beside the part's words the model writes what
is on the stage (``elements``: outcomes in a set, axes and a curve on them, a sentence
whose words can be pointed at, a formula whose terms are colored like the things they
count) and how it changes (``steps``: show, hide, highlight, color, move, transform, set).
The first step plays as the part begins; each later one belongs to words of the narration
that the model marks in [brackets], and plays when the narrator reaches them.

The core lays the elements out, writes the scene from templates, and has it paced by those
words: a Wanim storyboard of one phase per step, run in its slides mode (``pacing:
cued``), which holds after each phase until the host says ``next``. Each phase ends with
``post_message("step", n)``, so that the host knows when a step is done. A slide with a
slider ends on a live page where the learner moves it.

Nothing of the model's text reaches the scene but as a quoted literal, and a formula only
as Python written again by the figures module (ADR-045). An element that cannot be drawn,
and an action that names nothing on the stage, are left out and said: a picture is not
lost for one of its parts. The scene written passes the scene policy, here and again where
every scene does.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, ValidationError

from adle_core.generation.figures import (
    _IN_TEXT,
    FigureError,
    Number,
    _cell,
    _function,
    _on_axis,
    _plain,
    _py,
    _python_expression,
    _range,
    _samples,
    _tex,
    _tex_parts,
    _tick_pairs,
    _tried,
    _without_blanks,
)
from adle_core.generation.scene_policy import check_scene_source
from adle_core.generation.speech import UNICODE_TEX

#: The most elements a slide draws, and the most steps it takes (a live page besides).
MAX_ELEMENTS = 18
MAX_STEPS = 9

#: Colors a script may name, and the hue of the stage each stands for.
COLORS: dict[str, str] = {
    "blue": "blue", "green": "green", "yellow": "sun", "gold": "sun", "orange": "orange",
    "red": "coral", "pink": "coral", "coral": "coral", "purple": "violet", "violet": "violet",
    "teal": "teal", "cyan": "teal", "gray": "muted", "grey": "muted", "white": "ink",
    "black": "ink", "ink": "ink",
}  # fmt: skip
#: The same hues inside a formula, as they read on the lesson's dark screen (ADR-035).
TEX_COLORS: dict[str, str] = {
    "blue": "#7BA4EE", "green": "#3DBE7F", "sun": "#E9BE5A", "orange": "#F0A45D",
    "coral": "#F08F7D", "violet": "#A694E3", "teal": "#4FC3C9", "muted": "#9DB0A5",
    "ink": "#E7EFE9",
}  # fmt: skip
#: Hues given in turn to what the script did not color, so that things can be told apart.
_TURNS = ("blue", "green", "violet", "orange", "teal", "coral")

#: The safe area of the stage, and the room a slider takes at its foot.
_HALF_W, _HALF_H, _SLIDER_ROOM = 6.2, 3.4, 0.95

_SIZES = {"small": 0, "normal": 1, "large": 2}
_TEXT_SIZES = (28, 34, 44)
#: TeX is drawn about two thirds the size of text at one font size, in the pinned runtime
#: (seen side by side, 2026-11-22): formulas, numbers and words set in TeX are made larger by
#: this much to stand beside text as its equals.
_TEX_SCALE = 1.45
_MATH_SIZES = (42, 52, 66)

_REGIONS: dict[str, tuple[int, int]] = {
    "top left": (0, 0), "top": (0, 1), "top right": (0, 2),
    "left": (1, 0), "center": (1, 1), "right": (1, 2),
    "bottom left": (2, 0), "bottom": (2, 1), "bottom right": (2, 2),
}  # fmt: skip
_REGION_WORDS = {
    "centre": "center", "middle": "center", "upper left": "top left", "upper right": "top right",
    "lower left": "bottom left", "lower right": "bottom right", "upper": "top", "lower": "bottom",
    "left side": "left", "right side": "right", "top center": "top", "bottom center": "bottom",
    "center left": "left", "center right": "right", "middle left": "left",
    "middle right": "right", "top middle": "top", "bottom middle": "bottom", "up": "top",
    "down": "bottom", "below": "bottom", "under": "bottom", "beneath": "bottom",
    "above": "top", "over": "top",
}  # fmt: skip
#: Beside another element: the side, as ``beside`` in the scene numbers them.
_RELATIONS = {"below": 0, "above": 1, "left of": 2, "right of": 3}
_RELATION_WORDS = {
    "under": "below", "beneath": "below", "over": "above", "on top of": "above",
    "left": "left of", "right": "right of", "to the left of": "left of",
    "to the right of": "right of", "beside": "right of", "next to": "right of",
}  # fmt: skip
_SIDES = {
    "below": "DOWN", "under": "DOWN", "bottom": "DOWN", "down": "DOWN", "above": "UP",
    "over": "UP", "top": "UP", "up": "UP", "left": "LEFT", "right": "RIGHT",
}  # fmt: skip

#: How tall and how wide an element would like to be, in rough lines of text: the share of
#: the stage each is given.
_TALL = {
    "text": 1.0, "math": 1.3, "box": 1.4, "words": 1.2, "number": 1.0, "coin": 1.5,
    "die": 1.5, "dot": 0.6, "shape": 1.8, "set": 3.0, "grid": 3.4, "table": 3.0,
    "axes": 4.4, "number_line": 1.4, "bars": 3.6, "nodes": 3.0,
}  # fmt: skip
_WIDE = {
    "text": 1.6, "math": 1.4, "box": 1.4, "words": 2.0, "number": 0.9, "coin": 0.8,
    "die": 0.8, "dot": 0.4, "shape": 1.0, "set": 2.0, "grid": 2.0, "table": 2.4,
    "axes": 2.6, "number_line": 2.4, "bars": 2.4, "nodes": 2.4,
}  # fmt: skip


class SlideError(ValueError):
    """A slide that cannot be drawn at all, with the reasons."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


# -- reading what the model wrote ----------------------------------------------------------------


def _words(value: object) -> str:
    return " ".join(str(value).lower().replace("_", " ").replace("-", " ").split())


def _region(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    name = _REGION_WORDS.get(_words(value), _words(value))
    return name if name in _REGIONS else None


def _relation(value: object) -> tuple[int, str] | None:
    """Beside another element: ``{"below": "omega"}``, as (side, element)."""
    if isinstance(value, dict) and len(value) == 1:
        ((key, ref),) = value.items()
        relation = _RELATION_WORDS.get(_words(key), _words(key))
        if relation in _RELATIONS and isinstance(ref, str) and ref.strip():
            return (_RELATIONS[relation], ref.strip())
    return None


def _color(value: object) -> str | None:
    """A color by its name, as the stage's hue for it; None for a name there is not."""
    return COLORS.get(_words(value)) if isinstance(value, str) else None


def _size(value: object) -> int:
    if not isinstance(value, str):
        return 1
    name = _words(value)
    name = {"medium": "normal", "big": "large", "tiny": "small", "huge": "large"}.get(name, name)
    return _SIZES.get(name, 1)


def _tex_colors(tex: str) -> str:
    """Colors named in a formula (``\\color{yellow}``) as the hues of the stage; a color
    that is not one of them is left out, and what it colored stays."""

    def hue(match: re.Match[str]) -> str:
        name = COLORS.get(_words(match.group(2)))
        if name:
            return f"\\{match.group(1)}{{{TEX_COLORS[name]}}}"
        return "" if match.group(1) == "color" else "\\textcolor{" + TEX_COLORS["ink"] + "}"

    return re.sub(r"\\(color|textcolor)\{([A-Za-z ]{1,12})\}", hue, tex)


def _math(text: str) -> str:
    """A formula a script wrote, checked and ready to draw: or ValueError."""
    tex = _tex_colors(_tex(text))
    if re.search(r"\\(?:color|textcolor)\{(?!#[0-9A-F]{6}\})", tex):
        raise ValueError("colors a formula in a way it cannot be drawn")
    return tex


def _content(text: str) -> list[Any]:
    """Words, a formula, or both, as ``[is a formula, what is drawn]`` (``figures._cell``):
    TeX without dollar signs, and mathematics in its own symbols, are set as formulas."""
    spec = _cell(text)
    if spec[0]:
        spec[1] = _tex_colors(spec[1])
    return spec


#: A short name that reads as mathematics: a letter, a pair, a subscript, a number.
_TOKEN_MATH = re.compile(r"[A-Za-z]|[A-Za-z0-9(),.+\-=_^{}|/*<>' ]{1,14}")


def _token(text: str) -> list[Any]:
    """A short name for something on the stage: a formula when it reads as one (H, (1,2),
    x_1, 1/2), words when it is words."""
    text = " ".join(str(text).split())
    if not text:
        raise ValueError("must say something")
    if "$" in text or "\\" in text or any(char in UNICODE_TEX for char in text):
        return [True, _math(text)]
    # A name of letters alone is a name ("HH", "TT", "fib"), upright: set as a formula it
    # would read as letters multiplied. One letter is a variable, and is set as one.
    if re.fullmatch(r"[A-Za-z]{2,}", text):
        return [False, _plain(text)[:40]]
    if _TOKEN_MATH.fullmatch(text) and not re.search(r"[A-Za-z]{3,}", text):
        return [True, _math(text)]
    return [False, _plain(text)[:40]]


def _key(text: str) -> str:
    """How a part is named in a step: as written, without dollar signs or outer spaces."""
    return " ".join(str(text).replace("$", "").split())


def _bare(text: str) -> str:
    """A word as it is looked for: in lower case, without its punctuation."""
    return re.sub(r"[^\w']", "", text).lower()


def _wrapped(text: str, width: int) -> list[str]:
    """Lines of about ``width`` characters, never breaking inside $...$, and breaking where
    the text itself breaks its lines."""
    lines: list[str] = []
    for paragraph in text.replace("\\n", "\n").split("\n"):
        start = len(lines)
        for piece in re.findall(r"\$[^$]*\$\S*|\S+", paragraph):
            if len(lines) > start and len(lines[-1]) + 1 + len(piece) <= width:
                lines[-1] += " " + piece
            else:
                lines.append(piece)
    return lines[:6] or [text]


def _first_settings(raw_steps: object) -> dict[str, str]:
    """The first words each element is set to by a step, by its id."""
    found: dict[str, str] = {}
    if not isinstance(raw_steps, list):
        return found
    for step in raw_steps:
        for action in step if isinstance(step, list) else [step]:
            if isinstance(action, dict) and isinstance(action.get("set"), str):
                value = action.get("to", action.get("value"))
                if isinstance(value, str) and value.strip():
                    found.setdefault(action["set"], value)
    return found


def _filled(raw: dict[str, Any], later: dict[str, str]) -> dict[str, Any]:
    """A sentence, a text or a formula written empty, to be filled by a later step, begins
    as that step will set it (a real model wrote one so, 2026-11-22)."""
    field_name = "tex" if _words(raw.get("kind", "")) in ("math", "formula", "equation") else "text"
    if str(raw.get(field_name) or "").strip() or raw.get("id") not in later:
        return raw
    return {**raw, field_name: later[str(raw["id"])]}


def _number(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("it is given yes or no, not a number")
    if isinstance(value, int | float) and math.isfinite(value) and abs(value) <= 1e6:
        return float(value)
    if isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            pass
        else:
            if math.isfinite(number) and abs(number) <= 1e6:
                return number
    raise ValueError("it is given something that is not a number")


Text_ = Annotated[str, StringConstraints(min_length=1, max_length=220)]
Short = Annotated[str, StringConstraints(min_length=1, max_length=80)]
#: A cell of a grid or a table, which may be empty.
Cell = Annotated[str, StringConstraints(max_length=80)]


class _Spec(BaseModel):
    # A field the format does not know is passed over; one it knows must be right.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, populate_by_name=True)


class _Element(_Spec):
    id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,23}$")]
    kind: str
    place: Any = None
    color: Any = None
    size: Any = None
    label: Short | None = None


class TextElement(_Element):
    kind: Literal["text"]
    text: Text_


class MathElement(_Element):
    kind: Literal["math"]
    tex: Text_


class BoxElement(_Element):
    kind: Literal["box"]
    text: Text_


class DotElement(_Element):
    kind: Literal["dot"]


class ShapeElement(_Element):
    kind: Literal["shape"]
    shape: Literal["circle", "square", "rectangle", "triangle"] = "circle"


class SetElement(_Element):
    kind: Literal["set"]
    items: list[Short] = Field(default_factory=list, max_length=16)


class GridElement(_Element):
    kind: Literal["grid"]
    rows: list[list[Cell]] = Field(min_length=1, max_length=8)
    row_labels: list[Short] = Field(default_factory=list, max_length=8)
    col_labels: list[Short] = Field(default_factory=list, max_length=8)


class ArrowElement(_Element):
    kind: Literal["arrow"]
    start: Short = Field(alias="from")
    end: Short = Field(alias="to")
    curved: bool = False


class LineElement(_Element):
    kind: Literal["line"]
    start: Short = Field(alias="from")
    end: Short = Field(alias="to")
    dashed: bool = False


class BraceElement(_Element):
    kind: Literal["brace"]
    over: Short | list[Short]
    side: str = "below"


class OutlineElement(_Element):
    kind: Literal["outline"]
    around: Short | list[Short]


class LabelElement(_Element):
    kind: Literal["label"]
    on: Short
    text: Text_
    side: str = "above"


class AxesElement(_Element):
    kind: Literal["axes"]
    x: list[Number] = Field(min_length=2, max_length=2)
    y: list[Number] | None = Field(default=None, min_length=2, max_length=2)
    x_label: Short | None = None
    y_label: Short | None = None


class CurveElement(_Element):
    kind: Literal["curve"]
    on: Short
    f: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    start: Number | None = Field(default=None, alias="from")
    end: Number | None = Field(default=None, alias="to")


class AreaElement(_Element):
    kind: Literal["area"]
    under: Short
    start: Number | Short = Field(alias="from")
    end: Number | Short = Field(alias="to")


class PointElement(_Element):
    kind: Literal["point"]
    on: Short
    x: Number | Short


class TangentElement(_Element):
    kind: Literal["tangent"]
    at: Short


class NumberLineElement(_Element):
    kind: Literal["number_line"]
    x: list[Number] = Field(min_length=2, max_length=2)


class VectorElement(_Element):
    kind: Literal["vector"]
    on: Short
    to: list[Number] = Field(min_length=2, max_length=2)
    start: list[Number] | None = Field(default=None, alias="from", min_length=2, max_length=2)


class BarsElement(_Element):
    kind: Literal["bars"]
    labels: list[Short] = Field(min_length=1, max_length=10)
    values: list[Number] = Field(min_length=1, max_length=10)


class TableElement(_Element):
    kind: Literal["table"]
    header: list[Cell] = Field(default_factory=list, max_length=5)
    rows: list[list[Cell]] = Field(min_length=1, max_length=8)


class WordsElement(_Element):
    kind: Literal["words"]
    text: Text_


class NodesElement(_Element):
    kind: Literal["nodes"]
    nodes: list[Short] = Field(min_length=1, max_length=10)
    #: Each a pair of nodes, by name or by number from 1 (two nodes may have one name).
    edges: list[list[Short | int]] = Field(default_factory=list, max_length=16)
    layout: str = "row"
    directed: bool = True


class NumberElement(_Element):
    kind: Literal["number"]
    value: Number | Short
    decimals: int = Field(default=2, ge=0, le=3)


class CoinElement(_Element):
    kind: Literal["coin"]
    face: Short = "H"


class DieElement(_Element):
    kind: Literal["die"]
    face: int = Field(default=1, ge=1, le=6)


class ParamElement(_Element):
    kind: Literal["param"]
    value: Number
    min: Number | None = None
    max: Number | None = None
    slider: bool = False


Element = Annotated[
    TextElement
    | MathElement
    | BoxElement
    | DotElement
    | ShapeElement
    | SetElement
    | GridElement
    | ArrowElement
    | LineElement
    | BraceElement
    | OutlineElement
    | LabelElement
    | AxesElement
    | CurveElement
    | AreaElement
    | PointElement
    | TangentElement
    | NumberLineElement
    | VectorElement
    | BarsElement
    | TableElement
    | WordsElement
    | NodesElement
    | NumberElement
    | CoinElement
    | DieElement
    | ParamElement,
    Field(discriminator="kind"),
]
_ELEMENT: TypeAdapter[Any] = TypeAdapter(Element)

KINDS = (
    "text", "math", "box", "dot", "shape", "set", "grid", "arrow", "line", "brace", "outline",
    "label", "axes", "curve", "area", "point", "tangent", "number_line", "vector", "bars",
    "table", "words", "nodes", "number", "coin", "die", "param",
)  # fmt: skip
_KIND_WORDS = {
    "formula": "math", "equation": "math", "tex": "math", "latex": "math", "sentence": "words",
    "numberline": "number_line", "plot": "curve", "graph": "curve", "function": "curve",
    "rect": "shape", "rectangle": "shape", "circle": "shape", "square": "shape",
    "triangle": "shape", "chart": "bars", "bar": "bars", "bar chart": "bars",
    "network": "nodes", "tree": "nodes", "flow": "nodes", "value": "param", "slider": "param",
    "parameter": "param", "region": "area", "marker": "point", "counter": "number",
    "matrix": "grid", "card": "box", "venn": "set", "sample space": "set", "caption": "text",
    "title": "text", "note": "text",
}  # fmt: skip
#: Kinds placed on the stage by region; the others are drawn by what they refer to.
_PLACED = frozenset(_TALL)
#: Kinds whose pieces come and go one at a time; the rest are shown whole.
_PIECEWISE = frozenset({"set", "grid", "table", "nodes", "bars"})
#: Kinds one of which may be turned into another ("transform").
_SINGLE = frozenset({"text", "math", "box", "words", "dot", "shape"})
#: Kinds drawn by what they join or point at, whose words are a piece of their own.
_LINKS = frozenset({"arrow", "line", "brace", "outline", "vector", "curve"})

VERBS = ("show", "hide", "highlight", "color", "move", "transform", "set")
_VERB_WORDS = {
    "reveal": "show", "draw": "show", "add": "show", "fade in": "show", "create": "show",
    "write": "show", "appear": "show", "remove": "hide", "fade out": "hide",
    "fadeout": "hide", "fadein": "show", "emphasize": "highlight", "indicate": "highlight",
    "focus": "highlight", "flash": "highlight", "point": "highlight", "recolor": "color",
    "colour": "color", "paint": "color", "animate": "set", "change": "set", "morph": "transform",
    "become": "transform", "turn into": "transform", "replace": "transform", "shift": "move",
    "flip": "set", "roll": "set", "update": "set",
}  # fmt: skip


def _node(element: NodesElement, ref: str | int) -> int | None:
    """Which node an edge names, counted from 0: by its number from 1, or its name."""
    if isinstance(ref, int) or (isinstance(ref, str) and ref.strip().isdigit()):
        number = int(ref)
        if 1 <= number <= len(element.nodes) and not (
            isinstance(ref, str) and _key(ref) in [_key(node) for node in element.nodes]
        ):
            return number - 1
    names = [_key(node) for node in element.nodes]
    return names.index(_key(str(ref))) if _key(str(ref)) in names else None


def _element(raw: object) -> _Element:
    """One element as the model wrote it, checked: or ValueError saying why not."""
    if not isinstance(raw, dict):
        raise ValueError("an element is an object with an id and a kind")
    written: dict[str, Any] = _without_blanks(raw)
    kind = _words(written.get("kind", ""))
    if kind in ("circle", "square", "rectangle", "triangle") and "shape" not in written:
        written["shape"] = kind
    kind = _KIND_WORDS.get(kind, kind).replace(" ", "_")
    if kind not in KINDS:
        raise ValueError(f'"{kind[:20]}" is not a kind of element')
    if "id" not in written and "name" in written:
        written["id"] = written["name"]
    # A model that names an item as a step will point at it ("omega.HH") wrote the name
    # of the part, not of the item: what follows the dot is the item, when every item of
    # the list is written so.
    for field_name in ("items", "nodes", "labels"):
        listed = written.get(field_name)
        if (
            isinstance(listed, list)
            and listed
            and all(
                isinstance(item, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*\.\S.*", item)
                for item in listed
            )
        ):
            written[field_name] = [item.split(".", 1)[1] for item in listed]
    try:
        element: _Element = _ELEMENT.validate_python({**written, "kind": kind})
    except ValidationError as error:
        first = error.errors(include_input=False, include_url=False)[0]
        where = ".".join(str(part) for part in first["loc"][1:]) or kind
        raise ValueError(f"{where}: {first['msg']}") from error
    return element


# -- what a compiled slide is --------------------------------------------------------------------


@dataclass
class CompiledSlide:
    #: The whole scene file.
    source: str
    #: How many steps it takes: the phases of its storyboard, the live page among them.
    steps: int
    #: It ends on a live page with a control the learner moves.
    interactive: bool
    #: What it shows, in words, said by Adle from the script: for anyone who cannot see it.
    described: str
    #: What was left out, and why.
    left_out: list[str] = field(default_factory=list)


@dataclass
class _Axes:
    x0: float
    x1: float
    y0: float
    y1: float
    given_y: bool
    x_step: float = 1.0
    y_step: float = 1.0
    #: It has an area on it, which is measured from zero.
    zero: bool = False


@dataclass(frozen=True)
class _Target:
    """What a step names: an element, or a part of one, as the keys of ``self.e`` it is."""

    element: str
    keys: tuple[str, ...]
    whole: bool


@dataclass
class _Action:
    verb: str
    targets: list[_Target]
    hue: str = "sun"
    #: move: a region, (side, target), or a target to move onto.
    place: Any = None
    #: transform: the element turned into.
    into: str = ""
    #: set: the value, the face, or the new words.
    value: Any = None


@dataclass
class _Box:
    x: float
    y: float
    w: float
    h: float

    def literal(self) -> str:
        return _py([round(self.x, 3), round(self.y, 3), round(self.w, 3), round(self.h, 3)])


@dataclass
class _Formula:
    """A formula as drawn: its parts, and which of them the script set apart in {{ }}."""

    parts: list[str]
    groups: list[int]


def _double_braces(tex: str) -> list[str]:
    """A formula cut at its ``{{ ... }}`` groups, as Wanim cuts one: a group opens at the
    start or after a space, and closes at the first ``}}`` outside any brace within it.
    The pieces alternate: outside a group, inside one, outside..."""
    pieces: list[str] = []
    current = ""
    inside = False
    depth = 0
    index = 0
    while index < len(tex):
        if tex[index] == "\\" and index + 1 < len(tex) and tex[index + 1] in "\\{}":
            current += tex[index : index + 2]
            index += 2
            continue
        if not inside and tex.startswith("{{", index) and (index == 0 or tex[index - 1].isspace()):
            pieces.append(current)
            current, inside, depth = "", True, 0
            index += 2
            continue
        if inside and tex.startswith("}}", index) and depth == 0:
            pieces.append(current)
            current, inside = "", False
            index += 2
            continue
        if inside and tex[index] == "{":
            depth += 1
        elif inside and tex[index] == "}":
            depth -= 1
        current += tex[index]
        index += 1
    pieces.append(current)
    return pieces if not inside else [tex]


def _formula(tex: str) -> _Formula:
    """A formula as its parts: what the script wrote between {{ and }}, and what lies
    between those, each checked. One the script did not cut is cut where an equals sign
    or a plus or minus between terms stands, so that a part kept from one form to the
    next is seen to stay (``figures._tex_parts``)."""
    pieces = _double_braces(tex)
    if len(pieces) > 1:
        parts: list[str] = []
        groups: list[int] = []
        try:
            for index, piece in enumerate(pieces):
                if not piece.strip():
                    continue
                if index % 2:
                    groups.append(len(parts))
                parts.append(_math(piece))
        except ValueError:
            pass
        else:
            return _Formula(parts, groups)
        tex = "".join(pieces)
    whole = _math(tex)
    return _Formula(_tex_parts(whole), [])


# -- the compiler ----------------------------------------------------------------------------------


class _Compiler:
    def __init__(self) -> None:
        self.elements: dict[str, _Element] = {}
        self.order: list[str] = []
        self.left_out: list[str] = []
        self.param: ParamElement | None = None
        self.axes: dict[str, _Axes] = {}
        #: A curve: (the index of its function, from, to, its axes, drawn in pieces).
        self.curves: dict[str, tuple[int, float, float, str, bool]] = {}
        self.functions: list[str] = []
        #: Elements drawn from a value that changes (the parameter, a point's place).
        self.follows: set[str] = set()
        #: Each element's parts, as a step names them, and the keys they are.
        self.parts: dict[str, dict[str, tuple[str, ...]]] = {}
        #: Each element's pieces, which come and go: its keys in ``self.e``.
        self.pieces: dict[str, list[str]] = {}
        self.math: dict[str, _Formula] = {}
        self.colors: dict[str, str] = {}
        self.turn = 0
        self.steps: list[list[_Action]] = []
        self.boxes: dict[str, _Box] = {}
        self.cells: dict[tuple[int, int], list[str]] = {}
        self.inherits: dict[str, str] = {}
        self.relative: dict[str, tuple[int, str]] = {}
        #: While settling, the elements already checked: one refers only to those.
        self.ready: set[str] | None = None

    # -- reading -----------------------------------------------------------------------------------

    def read(self, raw_elements: object, raw_steps: object = None) -> None:
        if not isinstance(raw_elements, list):
            raise SlideError(["a slide's elements are a list"])
        later = _first_settings(raw_steps)
        for raw in raw_elements[:MAX_ELEMENTS]:
            if isinstance(raw, dict):
                raw = _filled(raw, later)
            try:
                element = _element(raw)
            except ValueError as error:
                self.left_out.append(f"an element: {error}")
                continue
            if element.id in self.elements:
                self.left_out.append(f'a second element named "{element.id}"')
                continue
            if isinstance(element, ParamElement):
                if self.param is not None:
                    self.left_out.append(f'"{element.id}": a slide moves one value, not two')
                    continue
                self.param = element
            self.elements[element.id] = element
            self.order.append(element.id)
        if len(raw_elements) > MAX_ELEMENTS:
            self.left_out.append(f"the elements after the first {MAX_ELEMENTS}")

    def hue(self, element: _Element) -> str:
        named = _color(element.color)
        if named:
            return named
        default = self.default_hue(element)
        if default is not None:
            return default
        hue = _TURNS[self.turn % len(_TURNS)]
        self.turn += 1
        return hue

    @staticmethod
    def default_hue(element: _Element) -> str | None:
        if isinstance(element, (TextElement, MathElement, WordsElement, LabelElement)):
            return "ink"
        if isinstance(element, (BraceElement, LineElement, AxesElement, NumberLineElement)):
            return "muted"
        if isinstance(element, (OutlineElement, AreaElement, CoinElement, NumberElement)):
            return "sun"
        if isinstance(element, (PointElement, TangentElement)):
            return "coral"
        return None

    # -- settling what each refers to -------------------------------------------------------------

    def settle(self) -> None:
        """Check every element and name its parts, leaving out what refers to nothing: in
        the order written, so that an element refers only to those before it. Then find
        the ranges of the axes from what is drawn on them."""
        if self.param is not None:
            try:
                self.check(self.param)
            except ValueError as error:
                self.left_out.append(f'"{self.param.id}": {error}')
                del self.elements[self.param.id]
                self.order.remove(self.param.id)
                self.param = None
        kept: list[str] = []
        self.ready = set()
        for name in self.order:
            element = self.elements[name]
            try:
                if not isinstance(element, ParamElement):
                    self.check(element)
                self.name_parts(element)
            except (ValueError, FigureError) as error:
                self.left_out.append(f'"{name}": {error}')
                del self.elements[name]
                self.axes.pop(name, None)
                self.curves.pop(name, None)
                continue
            kept.append(name)
            self.ready.add(name)
        self.ready = None
        self.order = kept
        for axes in self.axes.values():
            self.finish_axes(axes)
        for name in self.order:
            element = self.elements[name]
            if not isinstance(element, ParamElement):
                self.colors[name] = self.hue(element)

    def refer(self, ref: str) -> _Target | None:
        """What a name in the script stands for: an element, or a part of one."""
        ref = _key(ref)
        names = [
            name
            for name in self.elements
            if (self.ready is None or name in self.ready) and name in self.pieces
        ]
        if ref in names:
            return _Target(ref, tuple(self.pieces[ref]), True)
        head, dot, rest = ref.partition(".")
        lowered = {name.lower(): name for name in names}
        if not dot:
            if ref.lower() in lowered:
                name = lowered[ref.lower()]
                return _Target(name, tuple(self.pieces[name]), True)
            return None
        element = head if head in names else lowered.get(head.lower())
        if element is None:
            # A part named after another element than its own ("omega.2" in a set called
            # "omega_die", as a real model wrote it, copying an example): the element whose
            # name begins so, or the one element that has such a part.
            similar = [name for name in names if name.lower().startswith(head.lower())]
            having = [
                name
                for name in names
                if rest in self.parts.get(name, {}) or rest.lower() in self.parts.get(name, {})
            ]
            if len(similar) == 1:
                element = similar[0]
            elif len(having) == 1:
                element = having[0]
            else:
                return None
        parts = self.parts.get(element, {})
        keys = None
        # A part written with a stray prefix ("sentence.s.1-2", copied from an example
        # that called its sentence "s"): the part is what follows it.
        for spelled in (rest, rest.split(".", 1)[1] if "." in rest else None):
            if spelled is None or keys is not None:
                continue
            keys = parts.get(spelled) or parts.get(spelled.lower()) or parts.get(_bare(spelled))
            if keys is None and isinstance(self.elements[element], WordsElement):
                keys = self.phrase(element, spelled)
            counted = re.fullmatch(r"(\d+)\.(\d+)", spelled)
            if keys is None and counted and isinstance(self.elements[element], GridElement):
                # A cell counted from 0, as a program counts ("array.0.2"): a 0 says so.
                row, column = int(counted.group(1)), int(counted.group(2))
                if 0 in (row, column):
                    keys = parts.get(f"{row + 1}.{column + 1}")
        if keys is None:
            return None
        return _Target(element, keys, False)

    def phrase(self, element: str, text: str) -> tuple[str, ...] | None:
        """A run of words of a sentence: "3-5", or the words themselves."""
        words = self.word_list(element)
        span = re.fullmatch(r"(\d+)\s*-\s*(\d+)", text)
        if span:
            first, last = sorted((int(span.group(1)), int(span.group(2))))
            if first >= 1 and last <= len(words):
                return tuple(f"{element}.{index}" for index in range(first, last + 1))
            return None
        wanted = [_bare(word) for word in text.split() if _bare(word)]
        if not wanted:
            return None
        bare = [_bare(word) for word in words]
        for start in range(len(bare) - len(wanted) + 1):
            if bare[start : start + len(wanted)] == wanted:
                return tuple(f"{element}.{start + 1 + index}" for index in range(len(wanted)))
        return None

    def word_list(self, element: str) -> list[str]:
        written = self.elements[element]
        assert isinstance(written, WordsElement)
        return written.text.replace("$", "").split()[:48]

    def known(self, ref: str) -> bool:
        return self.refer(ref) is not None

    def check(self, element: _Element) -> None:
        if isinstance(element, (ArrowElement, LineElement)):
            for ref in (element.start, element.end):
                if not self.known(ref):
                    raise ValueError(f'it joins "{ref[:24]}", which is not on the stage before it')
        elif isinstance(element, (BraceElement, OutlineElement)):
            refs = element.over if isinstance(element, BraceElement) else element.around
            listed = [refs] if isinstance(refs, str) else refs
            if not [ref for ref in listed if self.known(ref)]:
                raise ValueError("it is around nothing that is on the stage before it")
        elif isinstance(element, LabelElement):
            if not self.known(element.on):
                raise ValueError(
                    f'it names "{element.on[:24]}", which is not on the stage before it'
                )
            _content(element.text)
        elif isinstance(element, AxesElement):
            x0, x1 = sorted(element.x)
            if x1 - x0 < 1e-6:
                raise ValueError("its x axis has no length")
            if element.y is not None:
                y0, y1 = sorted(element.y)
                if y1 - y0 < 1e-6:
                    raise ValueError("its y axis has no length")
                self.axes[element.id] = _Axes(x0, x1, y0, y1, True)
            else:
                self.axes[element.id] = _Axes(x0, x1, math.inf, -math.inf, False)
            for label in (element.x_label, element.y_label):
                if label:
                    _token(label)
        elif isinstance(element, CurveElement):
            axes = self.axes.get(element.on)
            if axes is None or (self.ready is not None and element.on not in self.ready):
                raise ValueError(f'it is drawn on "{element.on[:24]}", which is not axes before it')
            start = axes.x0 if element.start is None else max(axes.x0, element.start)
            end = axes.x1 if element.end is None else min(axes.x1, element.end)
            if end - start < 1e-6:
                raise ValueError("it is drawn over nothing")
            source = _python_expression(element.f, self.param.id if self.param else None)
            values = _tried(_function(source), _samples(start, end), self.trial_values())
            index = len(self.functions)
            self.functions.append(f"    def f_{index}(self, x, p):\n        return {source}\n")
            self.curves[element.id] = (index, start, end, element.on, " if " in source)
            axes.y0 = min(axes.y0, *values)
            axes.y1 = max(axes.y1, *values)
            if re.search(r"\bp\b", source):
                self.follows.add(element.id)
        elif isinstance(element, AreaElement):
            if element.under not in self.curves:
                raise ValueError(f'it is under "{element.under[:24]}", which is not a curve')
            for bound in (element.start, element.end):
                if isinstance(bound, str) and not self.is_param(bound):
                    raise ValueError(f'it ends at "{bound[:24]}", not a number or the value')
            if (
                self.is_param(element.start)
                or self.is_param(element.end)
                or element.under in self.follows
            ):
                self.follows.add(element.id)
            self.axes[self.curves[element.under][3]].zero = True
        elif isinstance(element, PointElement):
            on = self.elements.get(element.on)
            if element.on not in self.curves and not (
                isinstance(on, NumberLineElement)
                and (self.ready is None or element.on in self.ready)
            ):
                raise ValueError(f'it is on "{element.on[:24]}", not a curve or a number line')
            if isinstance(element.x, str) and not self.is_param(element.x):
                raise ValueError(f'its x is "{element.x[:24]}", not a number or the value')
            # A point has a place of its own, which a step may move, or it follows the value.
            self.follows.add(element.id)
        elif isinstance(element, TangentElement):
            point = self.elements.get(element.at)
            if (
                not isinstance(point, PointElement)
                or point.on not in self.curves
                or (self.ready is not None and element.at not in self.ready)
            ):
                raise ValueError(f'it touches "{element.at[:24]}", not a point on a curve')
            self.follows.add(element.id)
        elif isinstance(element, VectorElement):
            axes = self.axes.get(element.on)
            if axes is None or (self.ready is not None and element.on not in self.ready):
                raise ValueError(f'it is drawn on "{element.on[:24]}", which is not axes')
            for corner in (element.to, element.start or [0.0, 0.0]):
                axes.y0, axes.y1 = min(axes.y0, corner[1]), max(axes.y1, corner[1])
                axes.x0, axes.x1 = min(axes.x0, corner[0]), max(axes.x1, corner[0])
        elif isinstance(element, NumberElement):
            if isinstance(element.value, str) and not self.is_param(element.value):
                raise ValueError(f'its value is "{element.value[:24]}", which is not a number')
            if isinstance(element.value, str):
                self.follows.add(element.id)
        elif isinstance(element, BarsElement):
            if len(element.values) != len(element.labels):
                raise ValueError("it has not one value for each label")
            for label in element.labels:
                _token(label)
        elif isinstance(element, NodesElement):
            for edge in element.edges:
                if len(edge) != 2 or None in (_node(element, edge[0]), _node(element, edge[1])):
                    raise ValueError("an edge joins nodes that are not among its nodes")
            for node in element.nodes:
                _token(node)
        elif isinstance(element, ParamElement):
            low = element.min if element.min is not None else min(0.0, element.value)
            high = element.max if element.max is not None else max(1.0, 2 * element.value)
            low, high = sorted((low, high))
            if high - low < 1e-9 or not low <= element.value <= high:
                raise ValueError("its value is not between its ends")
            element.min, element.max = low, high
        elif isinstance(element, GridElement):
            if any(len(row) == 0 for row in element.rows):
                raise ValueError("a row of it is empty")
            if max(len(row) for row in element.rows) > 8:
                raise ValueError("a row of it has more than eight cells")
            for cell in [cell for row in element.rows for cell in row if cell.strip()]:
                _token(cell)
        elif isinstance(element, TableElement):
            width = max([len(element.header), *[len(row) for row in element.rows]])
            if width == 0 or width > 5:
                raise ValueError("it has no columns, or more than five")
            for cell in [*element.header, *[cell for row in element.rows for cell in row]]:
                _content(cell)
        elif isinstance(element, MathElement):
            self.math[element.id] = _formula(element.tex)
        elif isinstance(element, (TextElement, BoxElement)):
            for line in _wrapped(element.text, 40):
                _content(line)
        elif isinstance(element, SetElement):
            for item in element.items:
                _token(item)
        elif isinstance(element, CoinElement):
            _token(element.face)
        if element.label and not isinstance(element, ParamElement):
            _token(element.label)
        if isinstance(
            element, (ArrowElement, LineElement, BraceElement, OutlineElement, LabelElement)
        ):
            # Drawn from what moves (a point that follows the value), it moves with it.
            for ref in self.references(element):
                found = self.refer(ref)
                if found is not None and found.element in self.follows:
                    self.follows.add(element.id)

    @staticmethod
    def references(element: _Element) -> list[str]:
        """The names an element is drawn from, as the script wrote them."""
        if isinstance(element, (ArrowElement, LineElement)):
            return [element.start, element.end]
        if isinstance(element, BraceElement):
            return [element.over] if isinstance(element.over, str) else list(element.over)
        if isinstance(element, OutlineElement):
            return [element.around] if isinstance(element.around, str) else list(element.around)
        if isinstance(element, LabelElement):
            return [element.on]
        return []

    def is_param(self, value: object) -> bool:
        return isinstance(value, str) and self.param is not None and value == self.param.id

    def trial_values(self) -> list[float]:
        param = self.param
        if param is None:
            return [0.0]
        low = param.min if param.min is not None else param.value
        high = param.max if param.max is not None else param.value
        return [low, param.value, high]

    @staticmethod
    def finish_axes(axes: _Axes) -> None:
        if not math.isfinite(axes.y0) or not math.isfinite(axes.y1):
            axes.y0, axes.y1 = -1.0, 1.0
        low, high = axes.y0, axes.y1
        if axes.zero:
            low, high = min(low, 0.0), max(high, 0.0)
        if not axes.given_y:
            # Room above a curve, and zero in sight when it is near.
            span = (high - low) or 1.0
            if 0 < low < 0.4 * high:
                low = 0.0
            if 0 > high > 0.4 * low:
                high = 0.0
            high += 0.08 * span
            low -= 0.0 if low == 0 else 0.05 * span
        if 0 < axes.x0 < 0.4 * axes.x1:
            axes.x0 = 0.0
        axes.x0, axes.x1, axes.x_step = _range(axes.x0, axes.x1, 6)
        axes.y0, axes.y1, axes.y_step = _range(low, high, 4)

    def name_parts(self, element: _Element) -> None:
        """Name an element's pieces (what comes and goes) and its parts (what a step may
        point at after a dot)."""
        name = element.id
        parts: dict[str, tuple[str, ...]] = {}

        def alias(text: str, keys: tuple[str, ...]) -> None:
            for spelled in (_key(text), _key(text).lower(), _bare(text)):
                if spelled:
                    parts.setdefault(spelled, keys)

        def numbered(keys: list[str], spelled: Sequence[str]) -> None:
            for index, text in enumerate(spelled):
                parts[str(index + 1)] = (keys[index],)
                alias(text, (keys[index],))

        if isinstance(element, SetElement):
            keys = [f"{name}.{index + 1}" for index in range(len(element.items))]
            self.pieces[name] = [f"{name}/frame", *([f"{name}/name"] if element.label else [])]
            self.pieces[name] += keys
            numbered(keys, element.items)
        elif isinstance(element, (GridElement, TableElement)):
            self.name_cells(element, parts, alias)
        elif isinstance(element, NodesElement):
            keys = [f"{name}.{index + 1}" for index in range(len(element.nodes))]
            edges = [f"{name}.e{index + 1}" for index in range(len(element.edges))]
            self.pieces[name] = [f"{name}/frame", *keys, *edges]
            numbered(keys, element.nodes)
            for index, (start, end) in enumerate(element.edges):
                ends = [element.nodes[_node(element, side) or 0] for side in (start, end)]
                for joiner in ("->", "-", " to ", ">", "→"):
                    for first, second in (
                        (_key(ends[0]), _key(ends[1])),
                        (_bare(ends[0]), _bare(ends[1])),
                    ):
                        parts.setdefault(f"{first}{joiner}{second}", (edges[index],))
                parts[f"e{index + 1}"] = (edges[index],)
        elif isinstance(element, BarsElement):
            keys = [f"{name}.{index + 1}" for index in range(len(element.labels))]
            self.pieces[name] = [f"{name}/frame", *keys]
            numbered(keys, element.labels)
        elif isinstance(element, (AxesElement, NumberLineElement)):
            self.pieces[name] = [f"{name}/body", f"{name}/frame"]
        elif isinstance(element, (CoinElement, DieElement)):
            self.pieces[name] = [f"{name}/body", *([f"{name}/frame"] if element.label else [])]
        elif isinstance(element, WordsElement):
            words = self.word_list(name)
            numbered([f"{name}.{index + 1}" for index in range(len(words))], words)
        elif isinstance(element, MathElement):
            formula = self.math[name]
            for number, index in enumerate(formula.groups):
                key = f"{name}.{number + 1}"
                parts[str(number + 1)] = (key,)
                parts.setdefault(_key(formula.parts[index]), (key,))
        elif element.kind in _LINKS and element.label:
            self.pieces[name] = [name, f"{name}/name"]
        self.parts[name] = parts
        self.pieces.setdefault(name, [name])

    def name_cells(
        self, element: GridElement | TableElement, parts: dict[str, tuple[str, ...]], alias: Any
    ) -> None:
        name = element.id
        if isinstance(element, GridElement):
            rows: list[list[str]] = list(element.rows)
            first = 1
            row_names, col_names = element.row_labels, element.col_labels
        else:
            rows = ([element.header] if element.header else []) + list(element.rows)
            first = 0 if element.header else 1
            row_names, col_names = [], list(element.header)
        columns = max(len(row) for row in rows)
        self.pieces[name] = [f"{name}/frame"]
        for r, row in enumerate(rows):
            for c in range(columns):
                key = f"{name}.{r + first}.{c + 1}"
                self.pieces[name].append(key)
                parts[f"{r + first}.{c + 1}"] = (key,)
                if c < len(row) and r + first > 0:
                    alias(row[c], (key,))
        body = [r for r in range(len(rows)) if r + first > 0]
        for r in body:
            keys = tuple(f"{name}.{r + first}.{c + 1}" for c in range(columns))
            for spelled in (
                f"row {r + first}",
                f"row.{r + first}",
                f"row{r + first}",
                f"r{r + first}",
            ):
                parts[spelled] = keys
            if r - (1 - first) < len(row_names) and r + first - 1 < len(row_names):
                alias(row_names[r + first - 1], keys)
        for c in range(columns):
            keys = tuple(f"{name}.{r + first}.{c + 1}" for r in range(len(rows)))
            for spelled in (
                f"col {c + 1}",
                f"col.{c + 1}",
                f"col{c + 1}",
                f"column {c + 1}",
                f"c{c + 1}",
            ):
                parts[spelled] = keys
            if c < len(col_names):
                alias(col_names[c], keys)

    # -- the steps ---------------------------------------------------------------------------------

    def plan(self, raw_steps: object) -> None:
        """The steps, each a list of actions, checked: an action that names nothing on the
        stage is left out. Steps past the last there is room for join the last."""
        if not isinstance(raw_steps, list) or not raw_steps:
            shown = [
                name for name in self.order if not isinstance(self.elements[name], ParamElement)
            ]
            raw_steps = [[{"show": shown}]]
        written: list[list[Any]] = []
        for raw in raw_steps:
            actions = raw if isinstance(raw, list) else [raw]
            if isinstance(raw, dict) and isinstance(raw.get("actions"), list):
                actions = raw["actions"]
            if len(written) < MAX_STEPS:
                written.append(list(actions))
            else:
                written[-1] += actions
        if len(raw_steps) > MAX_STEPS:
            self.left_out.append(f"the steps after the {MAX_STEPS}th joined it")
        self.steps = []
        for actions in written:
            step: list[_Action] = []
            for raw_action in actions[:10]:
                try:
                    step.append(self.action(raw_action))
                except ValueError as error:
                    self.left_out.append(f"an action: {error}")
            self.steps.append(step)
        while len(self.steps) > 1 and not self.steps[-1]:
            self.steps.pop()

    def action(self, raw: object) -> _Action:
        if not isinstance(raw, dict) or not raw:
            raise ValueError('an action is an object such as {"show": "id"}')
        written = dict(raw)
        verb: str | None = None
        target: Any = None
        for key in list(written):
            word = _VERB_WORDS.get(_words(key), _words(key))
            if word in VERBS:
                verb, target = word, written.pop(key)
                break
        if verb is None:
            named = written.get("action") or written.get("do") or written.get("verb")
            word = _VERB_WORDS.get(_words(named), _words(named)) if isinstance(named, str) else ""
            if word not in VERBS:
                raise ValueError("it does none of " + ", ".join(VERBS))
            verb = word
            target = (
                written.get("target") or written.get("id") or written.get("what")
                or written.get("element") or written.get("targets")
            )  # fmt: skip
        listed = target if isinstance(target, list) else [target]
        targets = []
        for ref in listed[:16]:
            if not isinstance(ref, str):
                continue
            found = self.refer(ref)
            if found is None:
                self.left_out.append(f'a step names "{ref[:24]}", which is not on the stage')
                continue
            targets.append(found)
        if not targets:
            raise ValueError(f"{verb}: nothing it names is on the stage")
        hue = (
            _color(written.get("color")) or _color(written.get("to")) or _color(written.get("with"))
            or _color(written.get("as")) or _color(written.get("hue"))
        )  # fmt: skip
        if verb == "color" and hue is None:
            raise ValueError("color: it names no color there is")
        action = _Action(verb, targets, hue or "sun")
        if verb == "move":
            place = written.get("to", written.get("place", written.get("into")))
            region = _region(place)
            relation = _relation(place)
            beside = self.refer(relation[1]) if relation is not None else None
            onto = self.refer(place) if isinstance(place, str) else None
            if region is not None:
                action.place = region
            elif relation is not None and beside is not None:
                action.place = (relation[0], beside)
            elif onto is not None:
                action.place = onto
            else:
                raise ValueError("move: it says no place there is")
        elif verb == "transform":
            into = written.get("into", written.get("to", written.get("target")))
            found = self.refer(into) if isinstance(into, str) else None
            if found is None or not found.whole:
                raise ValueError("transform: it turns into nothing that is an element")
            if len(targets) != 1 or not targets[0].whole:
                raise ValueError("transform: it turns one element into another")
            source, goal = self.elements[targets[0].element], self.elements[found.element]
            if source.kind not in _SINGLE or goal.kind not in _SINGLE:
                raise ValueError("transform: only text, formulas, words and shapes turn")
            if found.element == targets[0].element:
                raise ValueError("transform: it turns into itself")
            action.into = found.element
        elif verb == "set":
            value = written.get("to", written.get("value", written.get("face")))
            action.value = self.setting(targets[0], value)
            action.targets = targets[:1]
        return action

    def setting(self, target: _Target, value: object) -> Any:
        """What a "set" changes an element to, checked against what the element is."""
        element = self.elements[target.element]
        if isinstance(element, ParamElement):
            number = _number(value)
            assert element.min is not None
            assert element.max is not None
            return min(max(number, element.min), element.max)
        if isinstance(element, PointElement):
            number = _number(value)
            if element.on in self.curves:
                _, start, end, _, _ = self.curves[element.on]
                return min(max(number, start), end)
            line = self.elements[element.on]
            assert isinstance(line, NumberLineElement)
            low, high = sorted(line.x)
            return min(max(number, low), high)
        if isinstance(element, NumberElement):
            if element.id in self.follows:
                raise ValueError("set: that number follows the value already")
            return _number(value)
        if isinstance(element, CoinElement):
            return _token(str(value or "")[:12] or "H")
        if isinstance(element, DieElement):
            face = round(_number(value))
            if not 1 <= face <= 6:
                raise ValueError("set: a die shows 1 to 6")
            return face
        if isinstance(element, BarsElement):
            if not isinstance(value, list) or len(value) != len(element.values):
                raise ValueError("set: bars are given one value for each")
            return [_number(item) for item in value]
        if isinstance(element, MathElement):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("set: a formula is set to another formula")
            return _formula(value)
        if isinstance(element, (TextElement, BoxElement)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("set: text is set to other text")
            return [_content(line) for line in _wrapped(value, 40)]
        if isinstance(element, WordsElement):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("set: a sentence is set to another sentence")
            return value.replace("$", "")[:220].split()[:48]
        raise ValueError(f"set: a {element.kind} has nothing to set")

    # -- where things go ---------------------------------------------------------------------------

    def layout(self, has_slider: bool) -> None:
        """A box on the stage for each element placed by region. The stage is cut into
        three bands (top, middle, bottom) and each band into its left, center and right,
        each given room as what is in it needs."""
        inherited = self.inheritors()
        chosen = self.chosen_places()
        for name in self.order:
            element = self.elements[name]
            if element.kind not in _PLACED:
                continue
            if name in inherited:
                self.inherits[name] = inherited[name]
                continue
            relation = _relation(element.place)
            if relation is not None:
                ref = relation[1]
                if (
                    ref != name
                    and ref in self.elements
                    and self.elements[ref].kind in _PLACED
                    and (ref in self.boxes or ref in self.relative or ref in self.inherits)
                ):
                    self.relative[name] = relation
                    continue
            region = _region(element.place) or chosen.get(name, "center")
            self.cells.setdefault(_REGIONS[region], []).append(name)
            self.boxes[name] = _Box(0, 0, 0, 0)  # settled below
        top = _HALF_H
        bottom = -_HALF_H + (_SLIDER_ROOM if has_slider else 0.0)
        rows = sorted({row for row, _ in self.cells})
        if not rows:
            return
        tall = {
            row: max(self.weight(names) for (r, _), names in self.cells.items() if r == row)
            for row in rows
        }
        room = (top - bottom) - 0.35 * (len(rows) - 1)
        y = top
        for row in rows:
            height = room * tall[row] / sum(tall.values())
            middle = y - height / 2
            y -= height + 0.35
            columns = sorted(column for r, column in self.cells if r == row)
            wide = {
                column: max(self.wide(name) for name in self.cells[(row, column)])
                for column in columns
            }
            if columns == [0]:
                spans = [(-_HALF_W, -_HALF_W + 1.2 * _HALF_W)]
            elif columns == [2]:
                spans = [(_HALF_W - 1.2 * _HALF_W, _HALF_W)]
            else:
                spans = []
                width = 2 * _HALF_W - 0.5 * (len(columns) - 1)
                x = -_HALF_W
                for column in columns:
                    share = width * wide[column] / sum(wide.values())
                    spans.append((x, x + share))
                    x += share + 0.5
            for column, (left, right) in zip(columns, spans, strict=True):
                names = self.cells[(row, column)]
                box = _Box((left + right) / 2, middle, right - left, height)
                weight = self.weight(names)
                for name in names:
                    self.boxes[name] = _Box(box.x, box.y, box.w, box.h * self.tall(name) / weight)
                self.boxes[f"@{row}.{column}"] = box

    def chosen_places(self) -> dict[str, str]:
        """Places for a stage whose script gave none (a model asked not to think first
        often gives none, 2026-11-22): what is drawn on the left, and words and formulas
        on the right; all in the middle when the stage is only one or the other."""
        placed = [name for name in self.order if self.elements[name].kind in _PLACED]
        if any(self.elements[name].place is not None for name in placed):
            return {}
        wordy = {"text", "math", "box", "words", "number"}
        pictures = [name for name in placed if self.elements[name].kind not in wordy]
        words = [name for name in placed if self.elements[name].kind in wordy]
        if not pictures or not words:
            return {}
        return {**dict.fromkeys(pictures, "left"), **dict.fromkeys(words, "right")}

    def weight(self, names: list[str]) -> float:
        return sum(self.tall(name) for name in names) + 0.4 * (len(names) - 1)

    def tall(self, name: str) -> float:
        element = self.elements[name]
        if isinstance(element, (TextElement, BoxElement)):
            return _TALL[element.kind] * (0.6 + 0.4 * len(_wrapped(element.text, 40)))
        if isinstance(element, WordsElement):
            return _TALL["words"] * (0.6 + 0.4 * math.ceil(len(element.text) / 34))
        if isinstance(element, GridElement):
            return 0.6 + 0.62 * len(element.rows)
        if isinstance(element, TableElement):
            return 0.5 + 0.5 * (len(element.rows) + (1 if element.header else 0))
        return _TALL.get(element.kind, 1.0)

    def wide(self, name: str) -> float:
        element = self.elements[name]
        if isinstance(element, (TextElement, BoxElement, WordsElement)):
            return _WIDE[element.kind] * min(1.0, 0.4 + len(element.text) / 60)
        if isinstance(element, MathElement):
            length = sum(len(part) for part in self.math[name].parts)
            return _WIDE["math"] * min(1.4, 0.4 + length / 30)
        return _WIDE.get(element.kind, 1.0)

    def inheritors(self) -> dict[str, str]:
        """Elements an element turns into, which take its place unless given one of their
        own that is not the same as its."""
        found: dict[str, str] = {}
        for step in self.steps:
            for action in step:
                if action.verb != "transform":
                    continue
                source = action.targets[0].element
                goal = self.elements[action.into]
                origin = self.elements[source]
                if goal.place is None or goal.place == origin.place:
                    found.setdefault(action.into, found.get(source, source))
        return found

    def box_of(self, name: str) -> _Box:
        if name in self.boxes:
            return self.boxes[name]
        if name in self.inherits:
            return self.box_of(self.inherits[name])
        if name in self.relative:
            return self.box_of(self.relative[name][1])
        return _Box(0, 0, 2 * _HALF_W, 2 * _HALF_H)


# -- writing the scene -----------------------------------------------------------------------------

#: The pips of a die, by face, on a grid of -1, 0, 1.
_PIPS = {
    1: [[0, 0]], 2: [[-1, 1], [1, -1]], 3: [[-1, 1], [0, 0], [1, -1]],
    4: [[-1, 1], [1, 1], [-1, -1], [1, -1]], 5: [[-1, 1], [1, 1], [0, 0], [-1, -1], [1, -1]],
    6: [[-1, 1], [1, 1], [-1, 0], [1, 0], [-1, -1], [1, -1]],
}  # fmt: skip
#: How many columns a set of so many items is laid out in.
_SET_COLUMNS = {1: 1, 2: 2, 3: 3, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 3, 10: 5, 11: 4, 12: 4,
                13: 5, 14: 5, 15: 5, 16: 4}  # fmt: skip

_SETUP = """\
    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"
        self.teal = "#4FC3C9" if dark else "#2B9EA5"
        self.orange = "#F0A45D" if dark else "#E8893A"
        self.e = {{}}
        self.set_storyboard([{pages}])
"""

#: What every slide can call.
_BASE = """\
    def fit(self, m, w, h):
        if m.width > w:
            m.scale_to_fit_width(w)
        if m.height > h:
            m.scale_to_fit_height(h)
        return m

    def put(self, keys, box, cols):
        group = VGroup(*[self.e[key] for key in keys])
        if cols > 1:
            group.arrange_in_grid(rows=(len(keys) + cols - 1) // cols, cols=cols, buff=0.45)
        elif len(keys) > 1:
            group.arrange(DOWN, buff=0.45)
        self.fit(group, box[2], box[3])
        grow = min(1.35, 0.75 * box[2] / max(group.width, 0.01), 0.75 * box[3] / max(group.height, 0.01))
        if grow > 1:
            group.scale(grow)
        group.move_to([box[0], box[1], 0])

    def keep(self, m):
        # Inside the stage: smaller if it is larger, moved in where it sticks out.
        self.fit(m, 12.4, 6.8)
        dx = 0
        dy = 0
        if m.get_right()[0] > 6.2:
            dx = 6.2 - m.get_right()[0]
        if m.get_left()[0] < -6.2:
            dx = -6.2 - m.get_left()[0]
        if m.get_top()[1] > 3.4:
            dy = 3.4 - m.get_top()[1]
        if m.get_bottom()[1] < -3.4:
            dy = -3.4 - m.get_bottom()[1]
        m.shift(RIGHT * dx + UP * dy)

    def group(self, keys):
        return VGroup(*[self.e[key] for key in keys])

    def beside(self, keys, anchor, side):
        # Where a group goes beside another: 0 below it, 1 above, 2 left of it, 3 right.
        mine = self.group(keys)
        other = self.group(anchor)
        if side == 0:
            return [other.get_center()[0], other.get_bottom()[1] - 0.55 - mine.height / 2, 0]
        if side == 1:
            return [other.get_center()[0], other.get_top()[1] + 0.55 + mine.height / 2, 0]
        if side == 2:
            return [other.get_left()[0] - 0.55 - mine.width / 2, other.get_center()[1], 0]
        return [other.get_right()[0] + 0.55 + mine.width / 2, other.get_center()[1], 0]

    def shown(self, spec, size, hue):
        if spec[0]:
            return MathTex(spec[1], font_size=round(size * 1.45), color=hue)
        return Text(spec[1], font_size=size, color=hue)

    def lines(self, specs, size, hue):
        made = VGroup(*[self.shown(spec, size, hue) for spec in specs])
        if len(specs) > 1:
            made.arrange(DOWN, buff=0.14)
        return made

    def unmark(self):
        if len(self.rings) > 0:
            self.play(*[FadeOut(ring) for ring in self.rings], run_time=0.3)
        self.rings = []

    def ring(self, keys, hue):
        ring = SurroundingRectangle(self.group(keys), color=hue, buff=0.12, corner_radius=0.12)
        self.rings.append(ring)
        return Create(ring)

    def tint(self, m, hue, fill):
        look = m.copy()
        look.set_color(hue)
        if fill > 0:
            look.set_fill(hue, fill)
        return Transform(m, look)

    def shift_to(self, keys, point):
        mine = self.group(keys)
        dx = point[0] - mine.get_center()[0]
        dy = point[1] - mine.get_center()[1]
        return [self.e[key].animate.shift(RIGHT * dx + UP * dy) for key in keys]

    def follow(self):
        for key in self.followers:
            self.e[key].update(0)
"""

_CHIP = """\
    def chip(self, spec, hue, rounded):
        token = self.shown(spec, 32, self.ink)
        if rounded:
            r = token.width / 2 + 0.2
            if token.height / 2 + 0.2 > r:
                r = token.height / 2 + 0.2
            if r < 0.36:
                r = 0.36
            shape = Circle(radius=r, color=hue)
        else:
            shape = SurroundingRectangle(token, color=hue, buff=0.2, corner_radius=0.14)
        shape.set_fill(hue, 0.18)
        shape.move_to(token.get_center())
        return VGroup(shape, token)
"""

_ENDS = """\
    def ends(self, a, b):
        dx = b.get_center()[0] - a.get_center()[0]
        dy = b.get_center()[1] - a.get_center()[1]
        if abs(dx) * 0.6 >= abs(dy):
            if dx >= 0:
                return [a.get_right(), b.get_left()]
            return [a.get_left(), b.get_right()]
        if dy >= 0:
            return [a.get_top(), b.get_bottom()]
        return [a.get_bottom(), b.get_top()]
"""

_LIBRARY: dict[str, str] = {
    "link": """\
    def link(self, a, b, kind, hue):
        start = self.group(a)
        end = self.group(b)
        points = self.ends(start, end)
        if kind == 4:
            # Between two words of one line: an arc over them, from top to top.
            bend = -PI / 2.2
            if end.get_center()[0] < start.get_center()[0]:
                bend = PI / 2.2
            return CurvedArrow(start.get_top() + UP * 0.08, end.get_top() + UP * 0.08, color=hue, angle=bend)
        if kind == 1:
            return CurvedArrow(points[0], points[1], color=hue)
        if kind == 2:
            return DashedLine(points[0], points[1], color=hue)
        if kind == 3:
            return Line(points[0], points[1], color=hue)
        return Arrow(points[0], points[1], buff=0.12, color=hue, max_tip_length_to_length_ratio=0.25, max_stroke_width_to_length_ratio=10)

    def tag(self, line, spec):
        words = self.shown(spec, 26, self.ink)
        start = line.get_start()
        end = line.get_end()
        if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
            return words.next_to(line, UP, buff=0.12)
        return words.next_to(line, RIGHT, buff=0.12)
""",
    "set": """\
    def make_set(self, key, keys, specs, rows, cols, name, hue):
        chips = VGroup()
        for index in range(len(keys)):
            chip = self.chip(specs[index], hue, True)
            self.e[keys[index]] = chip
            chips.add(chip)
        if len(keys) > 1:
            chips.arrange_in_grid(rows=rows, cols=cols, buff=0.4)
        width = 2.2
        height = 1.6
        if len(keys) > 0:
            # The smallest oval around a block passes through its corners: half again as
            # wide and high, and a little more, holds them inside.
            width = chips.width * 1.42 + 0.6
            height = chips.height * 1.42 + 0.6
        frame = Circle(radius=1, color=hue).stretch_to_fit_width(width).stretch_to_fit_height(height)
        if len(keys) > 0:
            frame.move_to(chips.get_center())
        self.e[key + "/frame"] = frame
        whole = VGroup(frame, chips)
        if name:
            title = self.shown(name, 30, hue)
            title.move_to([frame.get_left()[0] + title.width / 2 + 0.1, frame.get_top()[1] + title.height / 2 + 0.08, 0])
            self.e[key + "/name"] = title
            whole.add(title)
        self.e[key] = whole
""",
    "grid": """\
    def make_grid(self, key, keys, specs, rows, cols, side, row_names, col_names, name, hue):
        cells = VGroup()
        for index in range(len(keys)):
            square = Square(side_length=side, color=self.muted)
            square.set_fill(hue, 0.08)
            token = self.shown(specs[index], 28, self.ink)
            self.fit(token, side - 0.16, side - 0.16)
            token.move_to(square.get_center())
            cell = VGroup(square, token)
            self.e[keys[index]] = cell
            cells.add(cell)
        cells.arrange_in_grid(rows=rows, cols=cols, buff=0)
        marks = VGroup()
        for index in range(len(row_names)):
            marks.add(self.shown(row_names[index], 26, self.muted).next_to(self.e[keys[index * cols]], LEFT, buff=0.2))
        for index in range(len(col_names)):
            marks.add(self.shown(col_names[index], 26, self.muted).next_to(self.e[keys[index]], UP, buff=0.2))
        if name:
            lift = 0.25
            if len(col_names) > 0:
                lift = 0.75
            marks.add(self.shown(name, 30, hue).next_to(cells, UP, buff=lift))
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(marks, cells)
""",
    "table": """\
    def make_table(self, key, keys, specs, places, rooms, rule, name, hue):
        cells = VGroup()
        for index in range(len(keys)):
            cell = self.shown(specs[index], 28, self.ink)
            self.fit(cell, rooms[index], 0.62)
            cell.move_to([places[index][0], places[index][1], 0])
            self.e[keys[index]] = cell
            cells.add(cell)
        marks = VGroup()
        if rule:
            marks.add(Line([rule[0], rule[2], 0], [rule[1], rule[2], 0], color=self.muted))
        if name:
            marks.add(self.shown(name, 30, hue).next_to(cells, UP, buff=0.3))
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(marks, cells)
""",
    "nodes": """\
    def make_nodes(self, key, keys, specs, rounds, places, edges, directed, name, hue):
        nodes = VGroup()
        for index in range(len(keys)):
            chip = self.chip(specs[index], hue, rounds[index])
            chip.move_to([places[index][0], places[index][1], 0])
            self.e[keys[index]] = chip
            nodes.add(chip)
        links = VGroup()
        for edge in edges:
            points = self.ends(self.e[keys[edge[1]]], self.e[keys[edge[2]]])
            if directed:
                link = Arrow(points[0], points[1], buff=0.08, color=self.muted, max_tip_length_to_length_ratio=0.25, max_stroke_width_to_length_ratio=10)
            else:
                link = Line(points[0], points[1], color=self.muted)
            self.e[edge[0]] = link
            links.add(link)
        marks = VGroup()
        if name:
            marks.add(self.shown(name, 30, hue).next_to(nodes, UP, buff=0.35))
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(marks, links, nodes)
""",
    "bars": """\
    def bar(self, x, height, width, shown, label, hue):
        rect = Rectangle(width=width, height=max(0.04, abs(height)), color=hue)
        rect.set_fill(hue, 0.6)
        rect.move_to([x, height / 2, 0])
        number = Text(shown, font_size=26, color=self.ink)
        if height >= 0:
            number.next_to(rect, UP, buff=0.12)
        else:
            number.next_to(rect, DOWN, buff=0.12)
        name = self.shown(label, 24, self.muted)
        self.fit(name, width + 0.5, 0.6)
        if height >= 0:
            name.move_to([x, -0.35, 0])
        else:
            name.move_to([x, 0.35, 0])
        return VGroup(rect, number, name)

    def bars(self, xs, heights, width, shown, labels, hue):
        made = VGroup(Line([xs[0] - width, 0, 0], [xs[len(xs) - 1] + width, 0, 0], color=self.muted))
        for index in range(len(xs)):
            made.add(self.bar(xs[index], heights[index], width, shown[index], labels[index], hue))
        return made

    def make_bars(self, key, keys, xs, heights, width, shown, labels, name, tallest, hue):
        made = self.bars(xs, heights, width, shown, labels, hue)
        self.e[key + "/base"] = made[0]
        for index in range(len(keys)):
            self.e[keys[index]] = made[index + 1]
        marks = VGroup(made[0])
        if name:
            title = self.shown(name, 30, hue)
            title.move_to([0, tallest + 0.75 + title.height / 2, 0])
            marks.add(title)
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(marks, *[self.e[item] for item in keys])

    def rebar(self, key, keys, xs, heights, width, shown, labels, hue):
        fresh = self.bars(xs, heights, width, shown, labels, hue)
        base = self.e[key + "/base"]
        fresh.scale(base.width / fresh[0].width)
        fresh.shift(RIGHT * (base.get_center()[0] - fresh[0].get_center()[0]) + UP * (base.get_center()[1] - fresh[0].get_center()[1]))
        return [Transform(self.e[keys[index]], fresh[index + 1]) for index in range(len(keys))]
""",
    "axes": """\
    def make_axes(self, key, xr, yr, size, xs, ys, cross, x_label, y_label):
        axes = Axes(x_range=xr, y_range=yr, x_length=size[0], y_length=size[1], axis_config={"color": self.muted, "include_tip": False})
        marks = VGroup()
        for tick in xs:
            marks.add(MathTex(tick[1], font_size=36, color=self.muted).next_to(axes.c2p(tick[0], yr[0]), DOWN, buff=0.15))
        for tick in ys:
            if tick[0] != yr[0]:
                marks.add(MathTex(tick[1], font_size=36, color=self.muted).next_to(axes.c2p(xr[0], tick[0]), LEFT, buff=0.15))
        if x_label:
            marks.add(self.shown(x_label, 28, self.ink).next_to(axes.c2p(xr[1], cross[1]), RIGHT, buff=0.2))
        if y_label:
            marks.add(self.shown(y_label, 28, self.ink).next_to(axes.c2p(cross[0], yr[1]), UP, buff=0.2))
        self.ax[key] = axes
        self.e[key + "/body"] = axes
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(axes, marks)
""",
    "curve": """\
    def plot(self, axes, index, a, b, hue, pieces):
        p = self.amount.get_value()
        if pieces:
            return axes.plot(lambda x: self.value(index, x, p), x_range=[a, b, (b - a) / 400], color=hue, use_smoothing=False)
        return axes.plot(lambda x: self.value(index, x, p), x_range=[a, b], color=hue)

    def make_curve(self, key, axes, index, a, b, hue, pieces, follows):
        if follows:
            self.e[key] = always_redraw(lambda: self.plot(axes, index, a, b, hue, pieces))
            self.followers.append(key)
        else:
            self.e[key] = self.plot(axes, index, a, b, hue, pieces)
""",
    "area": """\
    def area_shape(self, axes, index, low, high, a, b, hue):
        p = self.amount.get_value()
        lo = p if low is None else low
        hi = p if high is None else high
        if hi < lo:
            swap = lo
            lo = hi
            hi = swap
        lo = max(lo, a)
        hi = min(hi, b)
        if hi - lo < 0.001:
            hi = lo + 0.001
        points = [axes.c2p(lo, 0)]
        for step in range(41):
            x = lo + (hi - lo) * step / 40
            points.append(axes.c2p(x, self.value(index, x, p)))
        points.append(axes.c2p(hi, 0))
        return Polygon(*points, color=hue, fill_opacity=0.38, stroke_width=0)

    def make_area(self, key, axes, index, low, high, a, b, hue, follows):
        if follows:
            self.e[key] = always_redraw(lambda: self.area_shape(axes, index, low, high, a, b, hue))
            self.followers.append(key)
        else:
            self.e[key] = self.area_shape(axes, index, low, high, a, b, hue)
""",
    "point": """\
    def spot(self, on, index, x, a, b):
        if index < 0:
            return self.e[on].n2p(x)
        if x < a:
            x = a
        if x > b:
            x = b
        return self.ax[on].c2p(x, self.value(index, x, self.amount.get_value()))

    def marker(self, on, index, tracker, a, b, name, hue):
        dot = Dot(color=hue, radius=0.1).move_to(self.spot(on, index, tracker.get_value(), a, b))
        if name:
            return VGroup(dot, self.shown(name, 26, self.ink).next_to(dot, UP + RIGHT, buff=0.1))
        return VGroup(dot)

    def make_point(self, key, on, index, x, a, b, name, hue):
        tracker = self.amount
        if x is not None:
            tracker = ValueTracker(x)
        self.trackers[key] = tracker
        self.e[key] = always_redraw(lambda: self.marker(on, index, tracker, a, b, name, hue))
        self.followers.append(key)
""",
    "tangent": """\
    def touching(self, axes, index, tracker, a, b, hue):
        x = tracker.get_value()
        if x < a:
            x = a
        if x > b:
            x = b
        p = self.amount.get_value()
        h = (b - a) / 2000
        left = axes.c2p(x - h, self.value(index, x - h, p))
        right = axes.c2p(x + h, self.value(index, x + h, p))
        middle = axes.c2p(x, self.value(index, x, p))
        dx = right[0] - left[0]
        dy = right[1] - left[1]
        size = math.sqrt(dx * dx + dy * dy)
        if size < 0.000001:
            dx = 1
            dy = 0
            size = 1
        ux = dx / size * 1.8
        uy = dy / size * 1.8
        return Line([middle[0] - ux, middle[1] - uy, 0], [middle[0] + ux, middle[1] + uy, 0], color=hue)

    def make_tangent(self, key, axes, index, point, a, b, hue):
        tracker = self.trackers[point]
        self.e[key] = always_redraw(lambda: self.touching(axes, index, tracker, a, b, hue))
        self.followers.append(key)
""",
    "number_line": """\
    def make_number_line(self, key, xr, length, ticks, name):
        line = NumberLine(x_range=xr, length=length, include_numbers=False, color=self.muted)
        marks = VGroup()
        for tick in ticks:
            marks.add(MathTex(tick[1], font_size=36, color=self.muted).next_to(line.n2p(tick[0]), DOWN, buff=0.2))
        if name:
            marks.add(self.shown(name, 28, self.ink).next_to(line, RIGHT, buff=0.3))
        self.e[key + "/body"] = line
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(line, marks)
""",
    "vector": """\
    def make_vector(self, key, axes, start, end, name, hue):
        tail = self.ax[axes].c2p(start[0], start[1])
        tip = self.ax[axes].c2p(end[0], end[1])
        self.e[key] = Arrow(tail, tip, buff=0, color=hue, max_tip_length_to_length_ratio=0.2, max_stroke_width_to_length_ratio=10)
        if name:
            self.e[key + "/name"] = self.shown(name, 28, hue).next_to(tip, UP + RIGHT, buff=0.1)
""",
    "coin": """\
    def coin(self, spec, hue):
        disc = Circle(radius=0.6, color=hue)
        disc.set_fill(hue, 0.3)
        face = self.shown(spec, 40, self.ink)
        self.fit(face, 0.9, 0.8)
        face.move_to(disc.get_center())
        return VGroup(disc, face)

    def flip(self, key, spec, hue):
        body = self.e[key + "/body"]
        size = body.height
        middle = body.get_center()
        self.play(body.animate.stretch_to_fit_height(0.05), run_time=0.14)
        self.play(body.animate.stretch_to_fit_height(size), run_time=0.14)
        self.play(body.animate.stretch_to_fit_height(0.05), run_time=0.14)
        fresh = self.coin(spec, hue)
        fresh.scale_to_fit_height(size)
        fresh.move_to(middle)
        fresh.stretch_to_fit_height(0.05)
        body.become(fresh)
        self.play(body.animate.stretch_to_fit_height(size), run_time=0.2)
""",
    "die": """\
    def die(self, spots, hue):
        body = RoundedRectangle(corner_radius=0.16, width=1.1, height=1.1, color=hue)
        body.set_fill(hue, 0.22)
        made = VGroup(body)
        for spot in spots:
            made.add(Dot(color=self.ink, radius=0.09).move_to([spot[0] * 0.28, spot[1] * 0.28, 0]))
        return made

    def roll(self, key, spots, hue):
        body = self.e[key + "/body"]
        size = body.height
        middle = body.get_center()
        self.play(Rotate(body, angle=PI / 2), run_time=0.22)
        self.play(Rotate(body, angle=PI / 2), run_time=0.22)
        fresh = self.die(spots, hue)
        fresh.scale_to_fit_height(size)
        fresh.move_to(middle)
        body.become(fresh)
        self.play(body.animate.scale(1.12), run_time=0.14)
        self.play(body.animate.scale(1 / 1.12), run_time=0.14)
""",
}


@dataclass
class _Writer:
    """The lines of one method of the scene."""

    lines: list[str] = field(default_factory=list)

    def say(self, line: str) -> None:
        self.lines.append("        " + line)

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def _e(key: str) -> str:
    return f"self.e[{_py(key)}]"


def _columns(count: int, box: _Box) -> int:
    """How many columns things that share a place stand in: one under another up to three,
    then in rows as wide as the place is (eight coins of an example stood in one column)."""
    if count <= 3:
        return 1
    return max(2, min(count, round(math.sqrt(count * box.w / max(box.h, 0.5)))))


def _text_part(word: str) -> str:
    """A word as a part of a line of words: set as text, its marks escaped."""
    return "\\text{" + "".join(_IN_TEXT.get(char, char) for char in word) + "}"


def _shown_width(spec: list[Any] | None, size: int) -> float:
    """About how wide a piece of text or a formula is drawn, in the stage's units."""
    if not spec:
        return 0.0
    if spec[0]:
        visible = re.sub(r"\\text\{([^}]*)\}", lambda m: m.group(1), spec[1])
        visible = re.sub(r"\\[A-Za-z]+", "x", visible)
        visible = re.sub(r"[{}_^\\ ]", "", visible)
        return max(1, len(visible)) * 0.27 * size * 1.2 / 48
    return len(spec[1]) * 0.25 * size / 48


def _shown_number(value: float) -> str:
    return f"{value:.3g}"


def _node_places(count: int, edges: list[list[int]], layout: str) -> list[list[float]]:
    """Where each node stands, before the whole is fitted to its place: in a row, a
    column, a circle, or a tree with each node a level below the one it comes from."""
    if layout in ("column", "vertical", "stack", "down"):
        return [[0.0, round(1.4 * ((count - 1) / 2 - index), 3)] for index in range(count)]
    if layout in ("circle", "cycle", "ring", "loop"):
        radius = max(1.4, 0.55 * count)
        return [
            [
                round(radius * math.cos(math.pi / 2 - 2 * math.pi * index / count), 3),
                round(radius * math.sin(math.pi / 2 - 2 * math.pi * index / count), 3),
            ]
            for index in range(count)
        ]
    if layout in ("tree", "hierarchy", "levels", "layers"):
        level = [0] * count
        for _ in range(count):
            for a, b in edges:
                if a != b and level[b] < level[a] + 1 <= count:
                    level[b] = level[a] + 1
        depth = max(level) + 1
        places: list[list[float]] = []
        for index in range(count):
            row = [other for other in range(count) if level[other] == level[index]]
            position = row.index(index)
            places.append(
                [
                    round((position - (len(row) - 1) / 2) * 2.6, 3),
                    round(((depth - 1) / 2 - level[index]) * 1.6, 3),
                ]
            )
        return places
    return [[round((index - (count - 1) / 2) * 2.6, 3), 0.0] for index in range(count)]


class _Scene:
    """Writes the scene file for a settled script, keeping track, step by step, of what is
    on the stage: a step acts only on what is there, and brings on what it needs."""

    def __init__(self, compiler: _Compiler) -> None:
        self.c = compiler
        self.used: set[str] = set()
        self.on: set[str] = set()
        self.math = dict(compiler.math)
        self.words = {
            name: compiler.word_list(name)
            for name, element in compiler.elements.items()
            if isinstance(element, WordsElement)
        }
        self.word_lines: dict[str, list[int]] = {}
        self.rings = False
        self.param_value = compiler.param.value if compiler.param else 0.0
        self.bar_shape: dict[str, tuple[list[float], float, list[list[Any]], float]] = {}

    # -- building ----------------------------------------------------------------------------------

    def build(self) -> str:
        c = self.c
        out = _Writer(["    def build(self):"])
        out.say("self.e = {}")
        out.say("self.ax = {}")
        out.say("self.trackers = {}")
        out.say("self.rings = []")
        out.say("self.followers = []")
        out.say(f"self.amount = ValueTracker({_py(self.param_value)})")
        later: list[str] = []
        for name in c.order:
            element = c.elements[name]
            if element.kind in _PLACED:
                self.make(out, name, element)
            elif not isinstance(element, ParamElement):
                later.append(name)
        # Each placed where it goes: by region, beside another, or where it turns from.
        for (row, column), names in c.cells.items():
            box = c.boxes[f"@{row}.{column}"]
            out.say(f"self.put({_py(names)}, {box.literal()}, {_columns(len(names), box)})")
        for name in c.order:
            if name in c.relative:
                side, ref = c.relative[name]
                # As wide as the place of what it stands beside, at most.
                box = c.box_of(ref)
                if side in (0, 1):
                    out.say(f"self.fit({_e(name)}, {_py(round(box.w, 3))}, 6.8)")
                out.say(f"{_e(name)}.move_to(self.beside([{_py(name)}], [{_py(ref)}], {side}))")
                out.say(f"self.keep({_e(name)})")
            elif name in c.inherits:
                box = c.box_of(c.inherits[name])
                out.say(f"self.fit({_e(name)}, {_py(round(box.w, 3))}, {_py(round(box.h, 3))})")
                out.say(f"{_e(name)}.move_to({_e(c.inherits[name])}.get_center())")
        for name in later:
            self.make(out, name, c.elements[name])
        return out.text()

    def make(self, out: _Writer, name: str, element: _Element) -> None:
        c = self.c
        hue = f"self.{c.colors[name]}"
        size = _size(element.size)
        label = _token(element.label) if element.label else None
        if isinstance(element, TextElement):
            specs = [_content(line) for line in _wrapped(element.text, 40)]
            out.say(f"{_e(name)} = self.lines({_py(specs)}, {_TEXT_SIZES[size]}, {hue})")
        elif isinstance(element, MathElement):
            parts = _py(self.math[name].parts)
            out.say(f"{_e(name)} = MathTex(*{parts}, font_size={_MATH_SIZES[size]}, color={hue})")
            self.name_tex_parts(out, name)
        elif isinstance(element, BoxElement):
            self.make_box(
                out, _e(name), [_content(line) for line in _wrapped(element.text, 36)], size, hue
            )
        elif isinstance(element, WordsElement):
            self.word_lines[name] = self.make_words(
                out, _e(name), name, self.words[name], size, hue
            )
            self.name_words(out, name)
        elif isinstance(element, DotElement):
            radius = (0.09, 0.13, 0.18)[size]
            out.say(f"dot = Dot(color={hue}, radius={radius})")
            if label:
                out.say(
                    f"words = self.shown({_py(label)}, 28, self.ink).next_to(dot, DOWN, buff=0.15)"
                )
                out.say(f"{_e(name)} = VGroup(dot, words)")
            else:
                out.say(f"{_e(name)} = VGroup(dot)")
        elif isinstance(element, ShapeElement):
            self.make_shape(out, name, element, size, label, hue)
        elif isinstance(element, SetElement):
            self.used |= {"chip", "set"}
            keys = [f"{name}.{index + 1}" for index in range(len(element.items))]
            specs = [_token(item) for item in element.items]
            columns = _SET_COLUMNS.get(len(keys), 4)
            rows = max(1, math.ceil(len(keys) / columns))
            out.say(
                f"self.make_set({_py(name)}, {_py(keys)}, {_py(specs)}, {rows}, {columns}, "
                f"{_py(label)}, {hue})"
            )
        elif isinstance(element, GridElement):
            self.make_grid(out, name, element, label, hue)
        elif isinstance(element, TableElement):
            self.make_table(out, name, element, label, hue)
        elif isinstance(element, NodesElement):
            self.make_nodes(out, name, element, label, hue)
        elif isinstance(element, BarsElement):
            self.make_bars(out, name, element, label, hue)
        elif isinstance(element, AxesElement):
            self.make_axes(out, name, element)
        elif isinstance(element, NumberLineElement):
            self.used.add("number_line")
            low, high = sorted(element.x)
            start, end, step = _range(low, high, 6)
            box = c.box_of(name)
            room = _shown_width(label, 28) + 0.4 if label else 0.0
            length = round(max(3.0, min(11.4, box.w - 0.6 - room)), 2)
            ticks = _tick_pairs(start, end, step, 9)
            out.say(
                f"self.make_number_line({_py(name)}, {_py([start, end, step])}, {length}, "
                f"{_py(ticks)}, {_py(label)})"
            )
        elif isinstance(element, NumberElement):
            self.make_number(out, name, element, size, label, hue)
        elif isinstance(element, CoinElement):
            self.used.add("coin")
            out.say(f"{_e(name + '/body')} = self.coin({_py(_token(element.face))}, {hue})")
            self.caption(out, name, label)
        elif isinstance(element, DieElement):
            self.used.add("die")
            out.say(f"{_e(name + '/body')} = self.die({_py(_PIPS[element.face])}, {hue})")
            self.caption(out, name, label)
        elif isinstance(element, (ArrowElement, LineElement)):
            self.make_link(out, name, element, label, hue)
        elif isinstance(element, (BraceElement, OutlineElement)):
            self.make_around(out, name, element, label, hue)
        elif isinstance(element, LabelElement):
            found = c.refer(element.on)
            assert found is not None
            side = _SIDES.get(_words(element.side), "UP")
            follows = name in c.follows
            self.assign(
                out,
                name,
                f"self.shown({_py(_content(element.text))}, 26, {hue}).next_to("
                f"self.group({_py(list(found.keys))}), {side}, buff=0.14)",
                follows,
            )
            if not follows:
                out.say(f"self.keep({_e(name)})")
        elif isinstance(element, (CurveElement, AreaElement, PointElement, TangentElement)):
            self.make_on_axes(out, name, element, label, hue)
        elif isinstance(element, VectorElement):
            self.used.add("vector")
            out.say(
                f"self.make_vector({_py(name)}, {_py(element.on)}, "
                f"{_py(list(element.start or [0.0, 0.0]))}, {_py(list(element.to))}, "
                f"{_py(label)}, {hue})"
            )

    def make_box(
        self, out: _Writer, target: str, specs: list[list[Any]], size: int, hue: str
    ) -> None:
        out.say(f"inner = self.lines({_py(specs)}, {_TEXT_SIZES[size]}, self.ink)")
        out.say(f"frame = SurroundingRectangle(inner, color={hue}, buff=0.3, corner_radius=0.18)")
        out.say(f"frame.set_fill({hue}, 0.14)")
        out.say(f"{target} = VGroup(frame, inner)")

    def make_shape(
        self, out: _Writer, name: str, element: ShapeElement, size: int, label: Any, hue: str
    ) -> None:
        scale = (0.7, 1.0, 1.4)[size]
        shapes = {
            "circle": f"Circle(radius={_py(0.8 * scale)}, color={hue})",
            "square": f"Square(side_length={_py(1.6 * scale)}, color={hue})",
            "rectangle": f"Rectangle(width={_py(2.6 * scale)}, height={_py(1.5 * scale)}, color={hue})",
            "triangle": (
                f"Polygon([{_py(-0.95 * scale)}, {_py(-0.75 * scale)}, 0], "
                f"[{_py(0.95 * scale)}, {_py(-0.75 * scale)}, 0], [0, {_py(0.9 * scale)}, 0], "
                f"color={hue})"
            ),
        }
        out.say(f"shape = {shapes[element.shape]}")
        out.say(f"shape.set_fill({hue}, 0.22)")
        if label:
            out.say(f"words = self.shown({_py(label)}, 30, self.ink)")
            out.say("self.fit(words, shape.width - 0.2, shape.height - 0.2)")
            out.say("words.move_to(shape.get_center())")
            out.say(f"{_e(name)} = VGroup(shape, words)")
        else:
            out.say(f"{_e(name)} = VGroup(shape)")

    def make_number(
        self, out: _Writer, name: str, element: NumberElement, size: int, label: Any, hue: str
    ) -> None:
        follows = isinstance(element.value, str)
        value = self.param_value if follows else float(element.value)
        font = _TEXT_SIZES[size] + 6
        out.say(
            f"number = DecimalNumber({_py(value)}, num_decimal_places={element.decimals}, "
            f"font_size={round(font * _TEX_SCALE)}, color={hue})"
        )
        if follows:
            out.say("number.add_updater(lambda m: m.set_value(self.amount.get_value()))")
            out.say(f"self.followers.append({_py(name + '/value')})")
        out.say(f"{_e(name + '/value')} = number")
        if label:
            out.say(f"title = self.shown({_py(label)}, {font - 4}, self.ink)")
            out.say(
                f'equals = MathTex("=", font_size={round((font - 4) * _TEX_SCALE)}, color=self.ink)'
            )
            out.say(f"{_e(name)} = VGroup(title, equals, number).arrange(RIGHT, buff=0.2)")
        else:
            out.say(f"{_e(name)} = VGroup(number)")

    def make_axes(self, out: _Writer, name: str, element: AxesElement) -> None:
        self.used.add("axes")
        axes = self.c.axes[name]
        box = self.c.box_of(name)
        x_label = _token(element.x_label) if element.x_label else None
        y_label = _token(element.y_label) if element.y_label else None
        room = _shown_width(x_label, 28) + 0.35 if x_label else 0.0
        width = round(max(2.4, min(10.6, box.w - 1.1 - room)), 2)
        height = round(max(1.8, box.h - (1.15 if y_label else 0.75)), 2)
        cross = [_on_axis(axes.x0, axes.x1), _on_axis(axes.y0, axes.y1)]
        out.say(
            f"self.make_axes({_py(name)}, {_py([axes.x0, axes.x1, axes.x_step])}, "
            f"{_py([axes.y0, axes.y1, axes.y_step])}, {_py([width, height])}, "
            f"{_py(_tick_pairs(axes.x0, axes.x1, axes.x_step))}, "
            f"{_py(_tick_pairs(axes.y0, axes.y1, axes.y_step, 5))}, {_py(cross)}, "
            f"{_py(x_label)}, {_py(y_label)})"
        )

    def assign(self, out: _Writer, key: str, expression: str, follows: bool) -> None:
        """One piece made: drawn once, or, when what it is drawn from moves (the value, a
        point), drawn again as that moves (``always_redraw``)."""
        if follows:
            out.say(f"{_e(key)} = always_redraw(lambda: {expression})")
            out.say(f"self.followers.append({_py(key)})")
        else:
            out.say(f"{_e(key)} = {expression}")

    def make_link(
        self, out: _Writer, name: str, element: ArrowElement | LineElement, label: Any, hue: str
    ) -> None:
        self.used |= {"ends", "link"}
        start, end = self.c.refer(element.start), self.c.refer(element.end)
        assert start is not None
        assert end is not None
        if isinstance(element, ArrowElement):
            kind = 1 if element.curved else 0
            # From word to word of one sentence: drawn as an arc over the line, not
            # through the words between them.
            sentence = self.c.elements[start.element]
            if (
                start.element == end.element
                and isinstance(sentence, WordsElement)
                and not start.whole
                and not end.whole
            ):
                kind = 4
        else:
            kind = 2 if element.dashed else 3
        follows = name in self.c.follows
        self.assign(
            out,
            name,
            f"self.link({_py(list(start.keys))}, {_py(list(end.keys))}, {kind}, {hue})",
            follows,
        )
        if label:
            self.assign(out, name + "/name", f"self.tag({_e(name)}, {_py(label)})", follows)

    def make_around(
        self, out: _Writer, name: str, element: BraceElement | OutlineElement, label: Any, hue: str
    ) -> None:
        refs = element.over if isinstance(element, BraceElement) else element.around
        listed = [refs] if isinstance(refs, str) else refs
        keys = [key for ref in listed if (found := self.c.refer(ref)) for key in found.keys]
        follows = name in self.c.follows
        if isinstance(element, BraceElement):
            side = _SIDES.get(_words(element.side), "DOWN")
            self.assign(out, name, f"Brace(self.group({_py(keys)}), {side}, color={hue})", follows)
            if label:
                self.assign(
                    out,
                    name + "/name",
                    f"self.shown({_py(label)}, 28, self.ink).next_to({_e(name)}, {side}, buff=0.12)",
                    follows,
                )
                if not follows:
                    out.say(f"self.keep({_e(name + '/name')})")
        else:
            self.assign(
                out,
                name,
                f"SurroundingRectangle(self.group({_py(keys)}), color={hue}, buff=0.16, "
                "corner_radius=0.14)",
                follows,
            )
            if label:
                self.assign(
                    out,
                    name + "/name",
                    f"self.shown({_py(label)}, 28, {hue}).next_to({_e(name)}, UP, buff=0.1)",
                    follows,
                )

    def make_on_axes(
        self, out: _Writer, name: str, element: _Element, label: Any, hue: str
    ) -> None:
        c = self.c
        self.used.add("curve")
        follows = _py(name in c.follows)
        if isinstance(element, CurveElement):
            index, start, end, axes, pieces = c.curves[name]
            out.say(
                f"self.make_curve({_py(name)}, self.ax[{_py(axes)}], {index}, {_py(start)}, "
                f"{_py(end)}, {hue}, {_py(pieces)}, {follows})"
            )
            if label:
                out.say(
                    f"{_e(name + '/name')} = self.shown({_py(label)}, 28, {hue}).next_to("
                    f"self.ax[{_py(axes)}].c2p({_py(end)}, self.value({index}, {_py(end)}, "
                    "self.amount.get_value())), UP + RIGHT, buff=0.1)"
                )
                out.say(f"self.keep({_e(name + '/name')})")
        elif isinstance(element, AreaElement):
            self.used.add("area")
            index, start, end, axes, _ = c.curves[element.under]
            low = None if c.is_param(element.start) else float(element.start)
            high = None if c.is_param(element.end) else float(element.end)
            out.say(
                f"self.make_area({_py(name)}, self.ax[{_py(axes)}], {index}, {_py(low)}, "
                f"{_py(high)}, {_py(start)}, {_py(end)}, {hue}, {follows})"
            )
        elif isinstance(element, PointElement):
            self.used.add("point")
            x = None if c.is_param(element.x) else float(element.x)
            if element.on in c.curves:
                index, start, end, on, _ = c.curves[element.on]
            else:
                line = c.elements[element.on]
                assert isinstance(line, NumberLineElement)
                index, on = -1, element.on + "/body"
                start, end = sorted(line.x)
            out.say(
                f"self.make_point({_py(name)}, {_py(on)}, {index}, {_py(x)}, {_py(start)}, "
                f"{_py(end)}, {_py(label)}, {hue})"
            )
        elif isinstance(element, TangentElement):
            self.used.add("tangent")
            point = c.elements[element.at]
            assert isinstance(point, PointElement)
            index, start, end, axes, _ = c.curves[point.on]
            out.say(
                f"self.make_tangent({_py(name)}, self.ax[{_py(axes)}], {index}, "
                f"{_py(element.at)}, {_py(start)}, {_py(end)}, {hue})"
            )

    def caption(self, out: _Writer, name: str, label: list[Any] | None) -> None:
        if label:
            out.say(
                f"{_e(name + '/frame')} = self.shown({_py(label)}, 28, self.ink).next_to("
                f"{_e(name + '/body')}, DOWN, buff=0.2)"
            )
            out.say(f"{_e(name)} = VGroup({_e(name + '/body')}, {_e(name + '/frame')})")
        else:
            out.say(f"{_e(name)} = VGroup({_e(name + '/body')})")

    def make_words(
        self, out: _Writer, target: str, name: str, words: list[str], size: int, hue: str
    ) -> list[int]:
        """A sentence, each word a part that can be pointed at: a formula of words
        (``\\text{...}``) for each line, so that the words sit on one baseline. A sentence
        with a letter TeX might not set as written is set in the text face instead. Its
        lines are as long as its place is wide, and far enough apart for words put above
        or below its words."""
        font = round(_TEXT_SIZES[size] * _TEX_SCALE)
        limit = max(14, min(60, int(self.c.box_of(name).w / (0.0042 * font))))
        lines: list[list[str]] = [[]]
        width = 0
        for word in words:
            if lines[-1] and width + 1 + len(word) > limit:
                lines.append([])
                width = 0
            lines[-1].append(word)
            width += len(word) + 1
        labelled = any(
            isinstance(other, LabelElement) and other.on.split(".")[0] == name
            for other in self.c.elements.values()
        )
        spacing = 1.0 if labelled else 0.3
        if all(word.isascii() for word in words):
            texts = [[_text_part(word) for word in line] for line in lines]
            separator = 'arg_separator="\\\\ "'
            if len(texts) == 1:
                out.say(
                    f"{target} = MathTex(*{_py(texts[0])}, font_size={font}, color={hue}, {separator})"
                )
            else:
                out.say(
                    f"{target} = VGroup(*[MathTex(*line, font_size={font}, color={hue}, "
                    f"{separator}) for line in {_py(texts)}]).arrange(DOWN, buff={spacing})"
                )
        else:
            plain = [[_plain(word) for word in line] for line in lines]
            out.say(
                f"{target} = VGroup(*[VGroup(*[Text(word, font_size={_TEXT_SIZES[size]}, "
                f"color={hue}) for word in line]).arrange(RIGHT, buff=0.2) for line in "
                f"{_py(plain)}]).arrange(DOWN, buff={spacing})"
            )
        return [len(line) for line in lines]

    def name_words(self, out: _Writer, name: str) -> None:
        counts = self.word_lines[name]
        single = len(counts) == 1 and all(word.isascii() for word in self.words[name])
        index = 0
        for line, count in enumerate(counts):
            for position in range(count):
                index += 1
                where = f"[{position}]" if single else f"[{line}][{position}]"
                out.say(f"self.e[{_py(f'{name}.{index}')}] = {_e(name)}{where}")

    def name_tex_parts(self, out: _Writer, name: str) -> None:
        formula = self.math[name]
        for number, index in enumerate(formula.groups):
            out.say(f"self.e[{_py(f'{name}.{number + 1}')}] = {_e(name)}[{index}]")

    def make_grid(
        self, out: _Writer, name: str, element: GridElement, label: Any, hue: str
    ) -> None:
        self.used.add("grid")
        columns = max(len(row) for row in element.rows)
        keys: list[str] = []
        specs: list[list[Any]] = []
        for r, row in enumerate(element.rows):
            for col in range(columns):
                keys.append(f"{name}.{r + 1}.{col + 1}")
                filled = col < len(row) and row[col].strip()
                specs.append(_token(row[col]) if filled else [False, " "])
        longest = max(_shown_width(spec, 28) for spec in specs)
        side = round(min(1.3, max(0.72, longest + 0.34)), 2)
        row_names = [_token(text) for text in element.row_labels[: len(element.rows)]]
        col_names = [_token(text) for text in element.col_labels[:columns]]
        out.say(
            f"self.make_grid({_py(name)}, {_py(keys)}, {_py(specs)}, {len(element.rows)}, "
            f"{columns}, {side}, {_py(row_names)}, {_py(col_names)}, {_py(label)}, {hue})"
        )

    def make_table(
        self, out: _Writer, name: str, element: TableElement, label: Any, hue: str
    ) -> None:
        self.used.add("table")
        columns = max([len(element.header), *[len(row) for row in element.rows]])
        rows = ([element.header] if element.header else []) + list(element.rows)
        first = 0 if element.header else 1
        specs = [
            [_content(row[col]) if col < len(row) else [False, " "] for col in range(columns)]
            for row in rows
        ]
        needed = [
            max(1.3, max(_shown_width(row[col], 28) for row in specs) + 0.45)
            for col in range(columns)
        ]
        scale = min(1.0, 11.6 / sum(needed))
        widths = [item * scale for item in needed]
        left = -sum(widths) / 2
        xs = []
        for item in widths:
            xs.append(round(left + item / 2, 3))
            left += item
        height = 0.72
        keys, flat, places, rooms = [], [], [], []
        for r, row in enumerate(specs):
            for col in range(columns):
                keys.append(f"{name}.{r + first}.{col + 1}")
                flat.append(row[col])
                places.append([xs[col], round(-r * height, 3)])
                rooms.append(round(widths[col] - 0.25, 3))
        half = round(sum(widths) / 2, 3)
        rule = [-half, half, round(-height / 2, 3)] if element.header else []
        out.say(
            f"self.make_table({_py(name)}, {_py(keys)}, {_py(flat)}, {_py(places)}, "
            f"{_py(rooms)}, {_py(rule)}, {_py(label)}, {hue})"
        )

    def make_nodes(
        self, out: _Writer, name: str, element: NodesElement, label: Any, hue: str
    ) -> None:
        self.used |= {"chip", "nodes", "ends"}
        count = len(element.nodes)
        specs = [_token(node) for node in element.nodes]
        rounds = [len(_key(node)) <= 3 for node in element.nodes]
        edges = [[_node(element, a) or 0, _node(element, b) or 0] for a, b in element.edges]
        places = _node_places(count, edges, _words(element.layout))
        keys = [f"{name}.{index + 1}" for index in range(count)]
        links = [[f"{name}.e{index + 1}", a, b] for index, (a, b) in enumerate(edges)]
        out.say(
            f"self.make_nodes({_py(name)}, {_py(keys)}, {_py(specs)}, {_py(rounds)}, "
            f"{_py(places)}, {_py(links)}, {_py(element.directed)}, {_py(label)}, {hue})"
        )

    def make_bars(
        self, out: _Writer, name: str, element: BarsElement, label: Any, hue: str
    ) -> None:
        self.used.add("bars")
        every = list(element.values)
        for step in self.c.steps:
            for action in step:
                if action.verb == "set" and action.targets[0].element == name:
                    every += action.value
        unit = 3.0 / max(max(abs(value) for value in every), 1e-9)
        count = len(element.values)
        width = round(min(1.3, 8.0 / count * 0.6), 3)
        gap = round(min(9.6 / count, 2.2), 3)
        xs = [round((index - (count - 1) / 2) * gap, 3) for index in range(count)]
        labels = [_token(text) for text in element.labels]
        self.bar_shape[name] = (xs, width, labels, unit)
        keys = [f"{name}.{index + 1}" for index in range(count)]
        heights = [round(value * unit, 4) for value in element.values]
        top = round(max(0.0, *[value * unit for value in every]), 3)
        out.say(
            f"self.make_bars({_py(name)}, {_py(keys)}, {_py(xs)}, {_py(heights)}, {width}, "
            f"{_py([_shown_number(value) for value in element.values])}, {_py(labels)}, "
            f"{_py(label)}, {top}, {hue})"
        )

    # -- the steps ---------------------------------------------------------------------------------

    def step(self, number: int, actions: list[_Action]) -> str:
        out = _Writer([f"    def step_{number}(self):"])
        if number == 0:
            out.say("self.build()")
        elif self.rings:
            out.say("self.unmark()")
            self.rings = False
        for action in actions:
            getattr(self, f"do_{action.verb}")(out, action)
        out.say(f'self.post_message("step", {number})')
        return out.text()

    def pieces(self, target: _Target) -> list[str]:
        """What has to be on the stage for a target to be seen: its own pieces, or, for a
        part of a formula or a sentence, the whole of it."""
        if self.c.elements[target.element].kind in _PIECEWISE and not target.whole:
            return list(target.keys)
        return list(self.c.pieces[target.element])

    def frames(self, name: str) -> list[str]:
        return [key for key in self.c.pieces[name] if "/" in key]

    def needs(self, name: str) -> list[str]:
        """The pieces an element is drawn on or from, which come on with it."""
        c = self.c
        element = c.elements[name]
        found: list[str] = []
        for ref in c.references(element):
            target = c.refer(ref)
            if target is None:
                continue
            owner = c.elements[target.element]
            if owner.kind not in _PLACED:
                found += self.needs(target.element)
            if owner.kind in _PIECEWISE and not target.whole:
                found += self.frames(target.element)
            found += self.pieces(target)
        if isinstance(element, (CurveElement, VectorElement)):
            found += c.pieces[element.on]
        elif isinstance(element, AreaElement):
            found += [*self.needs(element.under), element.under]
        elif isinstance(element, PointElement):
            found += self.needs(element.on) if element.on in c.curves else []
            found += [element.on] if element.on in c.curves else c.pieces[element.on]
        elif isinstance(element, TangentElement):
            found += [*self.needs(element.at), element.at]
        return found

    def entrance(self, key: str) -> str:
        """How a piece comes on: written, drawn, grown or faded in, as suits it."""
        c = self.c
        owner = key.split("/")[0].split(".")[0]
        element = c.elements[owner]
        kind = element.kind
        piece = key[len(owner) :]
        if piece == "/body" and kind in ("axes", "number_line"):
            return f"Create({_e(key)})"
        if piece == "/frame" and kind == "set":
            return f"Create({_e(key)})"
        if piece.startswith("/"):
            return f"GrowFromCenter({_e(key)})" if piece == "/body" else f"FadeIn({_e(key)})"
        if piece.startswith(".e") and kind == "nodes":
            directed = isinstance(element, NodesElement) and element.directed
            return f"GrowArrow({_e(key)})" if directed else f"Create({_e(key)})"
        if piece and kind in ("set", "nodes"):
            return f"GrowFromCenter({_e(key)})"
        if piece:
            return f"FadeIn({_e(key)}, shift=UP * 0.15)"
        if key in c.follows:
            return f"FadeIn({_e(key)})"
        if kind in ("math", "words"):
            return f"Write({_e(key)})"
        if isinstance(element, TextElement):
            return (
                f"Write({_e(key)})"
                if len(element.text) <= 32
                else f"FadeIn({_e(key)}, shift=UP * 0.15)"
            )
        if kind in ("curve", "line", "outline"):
            return f"Create({_e(key)})"
        if isinstance(element, ArrowElement) and element.curved:
            return f"Create({_e(key)})"
        if kind in ("arrow", "vector"):
            return f"GrowArrow({_e(key)})"
        if kind in ("dot", "shape", "brace"):
            return f"GrowFromCenter({_e(key)})"
        return f"FadeIn({_e(key)}, shift=UP * 0.15)"

    def do_show(self, out: _Writer, action: _Action) -> None:
        coming: list[str] = []
        for target in action.targets:
            element = self.c.elements[target.element]
            wanted: list[str] = []
            if element.kind not in _PLACED:
                wanted += self.needs(target.element)
            if element.kind in _PIECEWISE and not target.whole:
                wanted += self.frames(target.element)
            wanted += self.pieces(target)
            for key in wanted:
                if key not in self.on and key not in coming:
                    coming.append(key)
        if not coming:
            return
        entrances = [self.entrance(key) for key in coming]
        self.on |= set(coming)
        run = self.show_time(entrances)
        if len(entrances) == 1:
            out.say(f"self.play({entrances[0]}, run_time={run})")
        else:
            lag = 0.12 if len(entrances) > 6 else 0.3
            out.say(
                f"self.play(LaggedStart({', '.join(entrances)}, lag_ratio={lag}), run_time={run})"
            )

    @staticmethod
    def show_time(entrances: list[str]) -> float:
        writes = sum(1 for entrance in entrances if entrance.startswith("Write"))
        return round(min(2.6, 0.9 + 0.12 * len(entrances) + 0.3 * writes), 2)

    def dependents(self, keys: set[str]) -> list[str]:
        """What is on the stage drawn on or from these pieces, and goes when they go."""
        found: list[str] = []
        gone = set(keys)
        changed = True
        while changed:
            changed = False
            for other in self.c.order:
                if self.c.elements[other].kind in _PLACED:
                    continue
                if isinstance(self.c.elements[other], ParamElement):
                    continue
                showing = [
                    key for key in self.c.pieces[other] if key in self.on and key not in gone
                ]
                if showing and set(self.needs(other)) & gone:
                    found += showing
                    gone |= set(showing)
                    changed = True
        return found

    def do_hide(self, out: _Writer, action: _Action) -> None:
        going: list[str] = []
        for target in action.targets:
            for key in self.pieces(target):
                if key in self.on and key not in going:
                    going.append(key)
        going += [key for key in self.dependents(set(going)) if key not in going]
        if not going:
            return
        self.on -= set(going)
        fades = ", ".join(f"FadeOut({_e(key)})" for key in going)
        out.say(f"self.play({fades}, run_time=0.6)")

    def ensure(self, out: _Writer, targets: list[_Target]) -> None:
        """What a step acts on is brought on first, if it is not there yet."""
        missing = [target for target in targets if not set(self.pieces(target)) <= self.on]
        if missing:
            self.do_show(out, _Action("show", missing))

    def do_highlight(self, out: _Writer, action: _Action) -> None:
        self.ensure(out, action.targets)
        rings: list[str] = []
        pops: list[str] = []
        for target in action.targets:
            keys = [key for key in target.keys if "/" not in key or target.whole]
            rings.append(f"self.ring({_py(keys)}, self.{action.hue})")
            kind = self.c.elements[target.element].kind
            if not target.whole or kind in ("dot", "shape", "coin", "die"):
                pops += [
                    f"{_e(key)}.animate.scale(1.12)" for key in keys if key not in self.c.follows
                ]
        self.rings = True
        out.say(f"self.play({', '.join(rings + pops)}, run_time=0.45)")
        if pops:
            back = ", ".join(pop.replace("scale(1.12)", "scale(1 / 1.12)") for pop in pops)
            out.say(f"self.play({back}, run_time=0.25)")

    def do_color(self, out: _Writer, action: _Action) -> None:
        self.ensure(out, action.targets)
        tints: list[str] = []
        for target in action.targets:
            element = self.c.elements[target.element]
            keys = list(target.keys)
            if target.whole and element.kind in _PIECEWISE:
                keys = [key for key in keys if "/" not in key]
            for key in keys:
                if key in self.c.follows:
                    continue
                piece = key[len(target.element) :]
                chip = element.kind in ("set", "grid", "nodes", "bars") and piece[:2] not in (
                    "",
                    ".e",
                )
                if chip and "/" not in piece:
                    tints.append(f"self.tint({_e(key)}[0], self.{action.hue}, 0.45)")
                else:
                    tints.append(f"self.tint({_e(key)}, self.{action.hue}, 0)")
        if tints:
            out.say(f"self.play({', '.join(tints)}, run_time=0.7)")

    def do_move(self, out: _Writer, action: _Action) -> None:
        """Move what is named; what is drawn from it (an arrow to it, a brace over it, a
        label on it) goes while it moves and is drawn again from where it lands."""
        self.ensure(out, action.targets)
        keys: list[str] = []
        for target in action.targets:
            for key in self.pieces(target):
                if key in self.on and key not in keys and key not in self.c.follows:
                    keys.append(key)
        if not keys:
            return
        attached = [key for key in self.dependents(set(keys)) if key not in self.c.follows]
        owners: list[str] = []
        for key in attached:
            owner = key.split("/")[0]
            if owner not in owners:
                owners.append(owner)
        if attached:
            fades = ", ".join(f"FadeOut({_e(key)})" for key in attached)
            out.say(f"self.play({fades}, run_time=0.3)")
        place = action.place
        if isinstance(place, str):
            box = self.region_box(place)
            point = f"[{_py(round(box.x, 3))}, {_py(round(box.y, 3))}, 0]"
        elif isinstance(place, tuple):
            side, anchor = place
            point = f"self.beside({_py(keys)}, {_py(list(anchor.keys))}, {side})"
        else:
            point = f"self.group({_py(list(place.keys))}).get_center()"
        out.say(f"self.play(*self.shift_to({_py(keys)}, {point}), run_time=1.0)")
        if attached:
            for owner in owners:
                self.make(out, owner, self.c.elements[owner])
            entrances = ", ".join(self.entrance(key) for key in attached)
            out.say(f"self.play({entrances}, run_time=0.6)")

    def region_box(self, region: str) -> _Box:
        row, column = _REGIONS[region]
        cell = self.c.boxes.get(f"@{row}.{column}")
        if cell is not None:
            return cell
        return _Box((-3.9, 0.0, 3.9)[column], (2.4, 0.0, -2.4)[row], 4.0, 2.0)

    def do_transform(self, out: _Writer, action: _Action) -> None:
        source = action.targets[0].element
        goal = action.into
        self.ensure(out, action.targets)
        if goal in self.on:
            out.say(
                f"self.play({_e(source)}.animate.move_to({_e(goal)}.get_center()).set_opacity(0), "
                "run_time=0.8)"
            )
            out.say(f"self.remove({_e(source)})")
        else:
            kinds = {self.c.elements[name].kind for name in (source, goal)}
            single = all(len(self.word_lines.get(name, [1])) == 1 for name in (source, goal))
            ascii_only = all(
                word.isascii() for name in (source, goal) for word in self.words.get(name, [])
            )
            matching = kinds <= {"math", "words"} and single and ascii_only
            how = "TransformMatchingTex" if matching else "ReplacementTransform"
            out.say(f"self.play({how}({_e(source)}, {_e(goal)}), run_time=1.4)")
            self.on.add(goal)
        self.on.discard(source)

    def do_set(self, out: _Writer, action: _Action) -> None:
        c = self.c
        name = action.targets[0].element
        element = c.elements[name]
        if isinstance(element, ParamElement):
            out.say(
                f"self.play(self.amount.animate.set_value({_py(action.value)}), run_time=2.0, "
                "rate_func=smooth)"
            )
            self.param_value = action.value
            return
        hue = f"self.{c.colors[name]}"
        self.ensure(out, action.targets)
        box = c.box_of(name)
        fit = f"self.fit(fresh, {_py(round(box.w, 3))}, {_py(round(box.h, 3))})"
        if isinstance(element, PointElement):
            out.say(
                f"self.play(self.trackers[{_py(name)}].animate.set_value({_py(action.value)}), "
                "run_time=1.6, rate_func=smooth)"
            )
        elif isinstance(element, NumberElement):
            out.say(
                f"self.play(ChangeDecimalToValue({_e(name + '/value')}, {_py(action.value)}), "
                "run_time=1.2)"
            )
        elif isinstance(element, CoinElement):
            out.say(f"self.flip({_py(name)}, {_py(action.value)}, {hue})")
        elif isinstance(element, DieElement):
            out.say(f"self.roll({_py(name)}, {_py(_PIPS[action.value])}, {hue})")
        elif isinstance(element, BarsElement):
            xs, width, labels, unit = self.bar_shape[name]
            heights = [round(value * unit, 4) for value in action.value]
            keys = [f"{name}.{index + 1}" for index in range(len(action.value))]
            out.say(
                f"self.play(*self.rebar({_py(name)}, {_py(keys)}, {_py(xs)}, {_py(heights)}, "
                f"{width}, {_py([_shown_number(value) for value in action.value])}, "
                f"{_py(labels)}, {hue}), run_time=1.4)"
            )
        elif isinstance(element, MathElement):
            self.math[name] = action.value
            size = _MATH_SIZES[_size(element.size)]
            out.say(f"fresh = MathTex(*{_py(action.value.parts)}, font_size={size}, color={hue})")
            out.say(fit)
            out.say(f"fresh.move_to({_e(name)}.get_center())")
            out.say(f"self.play(TransformMatchingTex({_e(name)}, fresh), run_time=1.4)")
            out.say(f"{_e(name)} = fresh")
            self.name_tex_parts(out, name)
        elif isinstance(element, (TextElement, BoxElement)):
            size = _TEXT_SIZES[_size(element.size)]
            if isinstance(element, TextElement):
                out.say(f"fresh = self.lines({_py(action.value)}, {size}, {hue})")
            else:
                self.make_box(out, "fresh", action.value, _size(element.size), hue)
            out.say(fit)
            out.say(f"fresh.move_to({_e(name)}.get_center())")
            out.say(f"self.play(FadeTransform({_e(name)}, fresh), run_time=1.0)")
            out.say(f"{_e(name)} = fresh")
        elif isinstance(element, WordsElement):
            before = self.word_lines[name]
            ascii_before = all(word.isascii() for word in self.words[name])
            self.words[name] = action.value
            after = self.make_words(out, "fresh", name, action.value, _size(element.size), hue)
            out.say(fit)
            out.say(f"fresh.move_to({_e(name)}.get_center())")
            ascii_after = all(word.isascii() for word in action.value)
            matching = len(before) == 1 and len(after) == 1 and ascii_before and ascii_after
            how = "TransformMatchingTex" if matching else "ReplacementTransform"
            out.say(f"self.play({how}({_e(name)}, fresh), run_time=1.4)")
            out.say(f"{_e(name)} = fresh")
            self.word_lines[name] = after
            self.name_words(out, name)

    # -- the live page ---------------------------------------------------------------------------

    def live(self, number: int) -> str:
        param = self.c.param
        assert param is not None
        assert param.min is not None
        assert param.max is not None
        label = _token(param.label or param.id)
        name = re.sub(r"[^A-Za-z0-9_]", "_", param.id)[:24] or "value"
        out = _Writer(["    def blueprint(self):"])
        if self.rings:
            out.say("for ring in self.rings:")
            out.say("    self.remove(ring)")
            out.say("self.rings = []")
        out.say('self.state = {"explored": False}')
        out.say(
            "knob = Slider(start=[-3.0, -3.05, 0], end=[3.0, -3.05, 0], "
            f"value_range=({_py(param.min)}, {_py(param.max)}), "
            f"init_value={_py(self.param_value)}, color=self.green)"
        )
        out.say(f"self.adle_controls = {{{_py(name)}: knob}}")
        out.say(f"title = self.shown({_py(label)}, 28, self.ink)")
        out.say("title.next_to(knob, LEFT, buff=0.35)")
        out.say(
            f"reading = DecimalNumber({_py(self.param_value)}, num_decimal_places=2, "
            "font_size=42, color=self.ink)"
        )
        out.say("reading.next_to(knob, RIGHT, buff=0.35)")
        out.say("")
        out.say("def moved(control, previous, value):")
        out.say("    self.amount.set_value(value)")
        out.say("    reading.set_value(value)")
        out.say("    self.follow()")
        out.say('    if not self.state["explored"]:')
        out.say('        self.state["explored"] = True')
        out.say('        self.post_message("explored", True)')
        out.say("")
        out.say("knob.on_input(moved)")
        out.say("self.add(knob, title, reading)")
        out.say(f'self.post_message("step", {number})')
        return out.text()


def _describe(compiler: _Compiler) -> str:
    """What a slide shows, in words, from its script: plain, and never more than it shows.
    A formula is kept as a formula, in dollar signs, as a lesson's text sets it."""
    said: list[str] = []

    def plain(text: str) -> str:
        return _plain(text.replace("$", ""))

    def named(text: str | None) -> str:
        if not text:
            return ""
        spec = _token(text)
        return f"${spec[1]}$" if spec[0] else spec[1]

    for name in compiler.order:
        element = compiler.elements[name]
        label = named(element.label)
        if isinstance(element, (TextElement, BoxElement, WordsElement)):
            said.append(f"“{plain(element.text)}”")
        elif isinstance(element, MathElement):
            # Its colors are the picture's, not something to read.
            tex = " ".join(compiler.math[name].parts)
            said.append("$" + re.sub(r"\\(?:text)?color\{#[0-9A-F]{6}\}", "", tex) + "$")
        elif isinstance(element, SetElement):
            items = ", ".join(named(item) for item in element.items)
            title = f"the set {label}" if label else "a set"
            said.append(f"{title} of {items}" if items else f"{title}, empty")
        elif isinstance(element, GridElement):
            columns = max(len(row) for row in element.rows)
            said.append(
                f"a grid of {len(element.rows)} by {columns}" + (f", {label}" if label else "")
            )
        elif isinstance(element, TableElement):
            heads = ", ".join(named(head) for head in element.header)
            said.append("a table" + (f" of {heads}" if heads else ""))
        elif isinstance(element, AxesElement):
            said.append("axes")
        elif isinstance(element, CurveElement):
            said.append(f"the curve {label}" if label else f"a curve of ${element.f}$")
        elif isinstance(element, AreaElement):
            said.append("the area under it")
        elif isinstance(element, (PointElement, DotElement)):
            said.append(f"the point {label}" if label else "a point")
        elif isinstance(element, TangentElement):
            said.append("the line touching the curve there")
        elif isinstance(element, VectorElement):
            said.append(
                (f"the arrow {label}" if label else "an arrow")
                + f" to $({element.to[0]:g}, {element.to[1]:g})$"
            )
        elif isinstance(element, NumberLineElement):
            low, high = sorted(element.x)
            said.append(f"a number line from {low:g} to {high:g}")
        elif isinstance(element, BarsElement):
            pairs = ", ".join(
                f"{named(text)}: {value:g}"
                for text, value in zip(element.labels, element.values, strict=True)
            )
            said.append(f"bars for {pairs}")
        elif isinstance(element, NodesElement):
            said.append("boxes for " + ", ".join(named(node) for node in element.nodes))
        elif isinstance(element, ShapeElement):
            said.append(f"a {element.shape}" + (f" for {label}" if label else ""))
        elif isinstance(element, (ArrowElement, LineElement)) and label:
            said.append(f"an arrow, {label}")
        elif isinstance(element, BraceElement) and label:
            said.append(f"a brace: {label}")
        elif isinstance(element, (LabelElement, OutlineElement)) and (
            label or isinstance(element, LabelElement)
        ):
            said.append(named(element.text) if isinstance(element, LabelElement) else label)
        elif isinstance(element, NumberElement):
            said.append(f"the number {label}" if label else "a number")
        elif isinstance(element, CoinElement):
            said.append("a coin" + (f", {label}" if label else ""))
        elif isinstance(element, DieElement):
            said.append("a die" + (f", {label}" if label else ""))
    said = [phrase for phrase in said if phrase][:12]
    if not said:
        return "A picture."
    if len(said) == 1:
        return f"Shows {said[0]}."
    return "Shows " + ", ".join(said[:-1]) + " and " + said[-1] + "."


def compile_slide(raw: object) -> CompiledSlide:
    """The scene file for a slide script, or SlideError when none of it can be drawn."""
    if not isinstance(raw, dict):
        raise SlideError(["a slide is an object with elements and steps"])
    compiler = _Compiler()
    compiler.read(raw.get("elements"), raw.get("steps"))
    compiler.settle()
    if not [name for name in compiler.order if compiler.elements[name].kind in _PLACED]:
        raise SlideError(["nothing on the slide could be drawn", *compiler.left_out[:4]])
    compiler.plan(raw.get("steps"))
    if not any(compiler.steps):
        compiler.plan(None)
    slider = compiler.param is not None and compiler.param.slider
    compiler.layout(slider)
    scene = _Scene(compiler)
    build = scene.build()
    steps = [scene.step(number, actions) for number, actions in enumerate(compiler.steps)]
    pages = [f"[None, self.step_{number}]" for number in range(len(steps))]
    live = ""
    if slider:
        live = scene.live(len(steps))
        pages.append("[self.blueprint, None]")
    helpers = [_BASE]
    if "chip" in scene.used:
        helpers.append(_CHIP)
    if "ends" in scene.used:
        helpers.append(_ENDS)
    helpers += [_LIBRARY[name] for name in _LIBRARY if name in scene.used]
    value = ""
    if compiler.functions:
        last = len(compiler.functions) - 1
        cases = "".join(
            f"        if index == {index}:\n            return self.f_{index}(x, p)\n"
            for index in range(last)
        )
        value = f"    def value(self, index, x, p):\n{cases}        return self.f_{last}(x, p)\n"
    source = (
        "from manim import *\nimport math\n\n\n"
        "class Slide(InteractiveScene):\n"
        '    """A picture drawn a step at a time, as the narration reaches each."""\n\n'
        + _SETUP.format(pages=", ".join(pages))
        + "\n"
        + "\n".join(helpers)
        + ("\n" + "\n".join(compiler.functions) if compiler.functions else "")
        + ("\n" + value if value else "")
        + "\n"
        + build
        + "\n"
        + "\n".join(steps)
        + ("\n" + live if live else "")
    )
    report = check_scene_source(source)
    if not report.ok:
        problems = [violation.message for violation in report.violations[:3]]
        raise SlideError(["the slide's scene did not pass the scene rules", *problems])
    return CompiledSlide(
        source=source,
        steps=len(pages),
        interactive=slider,
        described=_describe(compiler),
        left_out=compiler.left_out,
    )
