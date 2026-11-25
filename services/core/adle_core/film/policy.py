"""What a chapter of a film may be (ADR-065).

A chapter is a Python file a model wrote, and the film engine (ManimGX) runs it on this
computer: not in the player's frame, which is what keeps a lesson's scenes in (SECURITY.md).
What stands between a chapter and the computer is therefore this policy first, and it is
written to be that. Nothing is executed here. A chapter may use only what is listed, and
what is not listed cannot be named.

What a chapter may use
----------------------
* ``import manimgx as m``, ``import numpy as np``, ``import math``: these, under these names.
* One scene, a ``m.Scene``, with ``construct``; functions of its own; assignments; ``for``
  and ``if``.
* Of ``m``: the names in ``data/names.json`` (``api``), written down from the pinned engine
  by ``scripts/dev/film_names.py``. Files, pictures from files, sound, the voice, the
  typesetter's own language, the engine's settings, the film being made, and three
  dimensions are left out there.
* Of anything else: the members in that file, and what numbers, words, lists and arrays have.
* Of ``np`` and ``math``: arithmetic. Nothing of ``np`` that reads, writes, or looks at memory.

What it refuses, each a way out
-------------------------------
* Any other import, and any name that the file does not define and that is not listed.
* Every name and attribute that begins with an underscore: the way to Python's own machinery.
* A name of Python's own that is not listed can be neither used nor defined: a file cannot
  define ``open`` in one place to use the real one in another.
* Keywords that name a file, a folder of fonts or of packages, the voice, or code for the
  typesetter; ``**`` in a call; and those same names written as text.
* Text that holds an address, a path, or a command of a typesetter that reads a file.
* ``while``, ``with``, ``try``, ``raise``, ``global``, ``yield``, ``async``, ``match``,
  decorators, other classes, ``print``.

What it is not
--------------
The operating system's sandbox. Text put together as the file runs is not seen here; the
engine gives a typesetter text only escaped, so that text never becomes its code (tried by
hand, ADR-065). The engine is started with nothing of this computer's in its environment, a
proxy that leads nowhere and the network refused in its own process, in a folder of its
own, for a bounded time (``film.runtime``, ``film.script``).
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Final

MAX_SOURCE_CHARS: Final = 60_000
MAX_AST_NODES: Final = 12_000
MAX_STRING_CHARS: Final = 2_000
#: The longest line a chapter may say at once, and the most lines it may say.
MAX_LINE_CHARS: Final = 600
MAX_LINES: Final = 80
MAX_VIOLATIONS: Final = 20

#: The only imports, each under the only name it may have.
IMPORTS: Final = {"manimgx": "m", "numpy": "np", "math": None}
MODULE_NAMES: Final = frozenset({"m", "np", "math"})

#: Python's own names a chapter may use. Nothing that looks inside an object (getattr,
#: vars, type, dir), that runs text (eval, exec, compile), or that reaches outside (open,
#: input, print, __import__).
ALLOWED_BUILTINS: Final = frozenset(
    {
        "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "int",
        "isinstance", "len", "list", "map", "max", "min", "pow", "range", "reversed", "round",
        "set", "sorted", "str", "sum", "tuple", "zip", "complex",
        "True", "False", "None",
    }
)  # fmt: skip
#: Every name Python has of its own: one that is not allowed can be neither used nor bound.
_PYTHON_NAMES: Final = frozenset(dir(builtins))

#: Of numpy: making arrays and arithmetic on them.
NUMPY: Final = frozenset(
    {
        "array", "asarray", "linspace", "arange", "zeros", "ones", "full", "eye", "identity",
        "zeros_like", "ones_like", "full_like", "logspace", "geomspace", "meshgrid",
        "pi", "e", "inf", "nan", "newaxis", "float64", "float32", "int64", "int32",
        "sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2", "sinh", "cosh", "tanh",
        "exp", "exp2", "expm1", "log", "log2", "log10", "log1p", "sqrt", "cbrt", "square",
        "power", "abs", "absolute", "sign", "floor", "ceil", "round", "around", "rint",
        "trunc", "clip", "minimum", "maximum", "min", "max", "amin", "amax", "sum", "prod",
        "mean", "average", "median", "std", "var", "cumsum", "cumprod", "diff", "gradient",
        "dot", "cross", "outer", "inner", "matmul", "transpose", "concatenate", "stack",
        "vstack", "hstack", "column_stack", "tile", "repeat", "flip", "roll", "reshape",
        "ravel", "where", "select", "piecewise", "isclose", "allclose", "array_equal",
        "isnan", "isinf", "isfinite", "nan_to_num", "deg2rad", "rad2deg", "degrees",
        "radians", "hypot", "mod", "fmod", "remainder", "floor_divide", "interp", "polyfit",
        "polyval", "roots", "argsort", "sort", "unique", "argmax", "argmin", "count_nonzero",
        "real", "imag", "conj", "angle", "sinc", "heaviside", "trapezoid", "vectorize",
        "histogram", "linalg", "random",
    }
)  # fmt: skip
#: What ``np.linalg`` and ``np.random`` have that a chapter may use.
_NUMPY_INNER: Final = frozenset(
    {
        "norm", "inv", "det", "solve", "eig", "eigvals",
        "seed", "uniform", "normal", "randint", "rand", "randn", "choice", "shuffle",
        "permutation",
    }
)  # fmt: skip
MATH: Final = frozenset(name for name in dir(math) if not name.startswith("_"))

#: What numbers, words, lists, mappings and arrays have, beyond what the engine's own
#: things have: nothing that formats from a pattern, makes bytes, or looks at memory.
COMMON: Final = frozenset(
    {
        # words
        "join", "split", "rsplit", "splitlines", "strip", "lstrip", "rstrip", "upper",
        "lower", "title", "capitalize", "replace", "startswith", "endswith", "zfill",
        "rjust", "ljust", "center", "count", "index", "find", "isdigit", "isalpha",
        # lists, mappings, sets
        "append", "extend", "insert", "pop", "remove", "sort", "reverse", "copy", "clear",
        "get", "items", "keys", "values", "update", "setdefault", "add", "union",
        "intersection", "difference",
        # numbers and arrays
        "real", "imag", "conjugate", "T", "shape", "size", "ndim", "tolist", "sum", "mean",
        "min", "max", "dot", "flatten", "ravel", "reshape", "transpose", "round", "clip",
        "argmax", "argmin", "cumsum", "prod", "std", "any", "all", "astype", "item",
    }
)  # fmt: skip

#: A keyword that names a file, a folder, the voice, or code for the typesetter. A path an
#: animation follows is none of these.
_WAY_OUT_KEYWORD: Final = re.compile(
    r"(?i)file|path|preamble|package|voice|template|cache|sound|svg|image|config_file|typst"
)
_PATHS_THAT_ARE_NOT: Final = frozenset({"path_arc", "path_func", "path_arc_axis"})
#: A font is named by its family, never by where it is.
_PLAIN_VALUE: Final = {
    "font": re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{0,39}$"),
    "language": re.compile(r"^[A-Za-z0-9+#-]{1,20}$"),
    "tex_environment": re.compile(r"^[a-z*]{1,20}$"),
}

_URL_LIKE: Final = re.compile(
    r"(?i)(?:https?|wss?|ftp|file)://|\b(?:javascript|vbscript|blob):|\bdata:[a-z]+/|\bwww\.[a-z0-9-]+\.[a-z]"
)
#: Narrow on purpose: a formula says things like ``F:\ \text{newtons}`` and ``f:\mathbb{R}``,
#: which are not drives. A drive is a letter, a colon, and two steps of a path. And a formula
#: steps down with ``\\``, which is not a share.
_PATH_LIKE: Final = re.compile(
    r"(?:^|[\s\"'(=])[A-Za-z]:[\\/][A-Za-z0-9_][A-Za-z0-9_ .-]*[\\/]"  # a drive
    r"|(?:^|[\s\"'(=])\\\\[A-Za-z0-9_.$-]+\\[A-Za-z0-9_.$-]+"  # a share
    r"|(?:^|[\s\"'(=])(?:~|\.\.?)[\\/]"  # home, here, up
    r"|(?:^|[\s\"'(=])/(?:etc|usr|bin|home|var|tmp|proc|sys|dev|mnt|opt|root|Users|Library|Volumes)/"
)
#: Commands of TeX and of Typst that read or write a file, or run text.
_TYPESETTER_OUT: Final = re.compile(
    r"\\(?:input|include|openin|openout|write|read|immediate|csname|catcode|usepackage)\b"
    r"|#\s*(?:import|include|read|image|plugin|eval|sys|bytes|json|csv|toml|yaml|xml|cbor)\b"
)
_CONTROL: Final = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MARKUP: Final = re.compile(r"(?i)<\s*/?\s*(?:script|iframe|img|svg|a|div|span|p|br)\b")

_REFUSED_NODES: Final = {
    ast.While: "while",
    ast.With: "with",
    ast.AsyncWith: "async",
    ast.AsyncFor: "async",
    ast.AsyncFunctionDef: "async",
    ast.Await: "async",
    ast.Try: "try",
    ast.TryStar: "try",
    ast.Raise: "raise",
    ast.Assert: "assert",
    ast.Global: "global",
    ast.Nonlocal: "nonlocal",
    ast.Yield: "yield",
    ast.YieldFrom: "yield",
    ast.Match: "match",
    ast.ImportFrom: "from ... import",
}


@dataclass(frozen=True, slots=True)
class Violation:
    code: str
    #: What is wrong, said to whoever wrote the file so that they can mend it. It names the
    #: construct, never a learner's words.
    message: str
    line: int | None = None


@dataclass(frozen=True, slots=True)
class ChapterReport:
    ok: bool
    violations: tuple[Violation, ...]
    #: The name of its scene.
    scene_class: str | None
    #: What it says, a line at a time, as written: brackets and all.
    lines: tuple[str, ...]
    content_hash: str


@dataclass(frozen=True, slots=True)
class _Names:
    api: frozenset[str]
    members: frozenset[str]
    #: What the engine's own things have that a chapter may not use: none of these may be
    #: given to ``self`` under its name either.
    refused: frozenset[str]
    #: What a scene has of its own: a chapter does not replace any of it.
    scene: frozenset[str]
    version: str


@lru_cache(maxsize=1)
def names() -> _Names:
    raw = json.loads(
        resources.files("adle_core.film.data").joinpath("names.json").read_text(encoding="utf-8")
    )
    return _Names(
        api=frozenset(raw["api"]),
        members=frozenset(raw["members"]),
        refused=frozenset(raw["refused"]),
        scene=frozenset(raw["scene"]),
        version=str(raw["version"]),
    )


def normalise_source(source: str) -> str:
    """One way of writing the same file: its line ends, and one line end at its end."""
    return source.replace("\r\n", "\n").replace("\r", "\n").strip("\n") + "\n"


def said(text: str) -> str:
    """A line as it is spoken, one way of writing it: without the brackets that mark its
    animations, and with one space between its words. The voice is asked for this, and the
    engine's line is looked up by it (``film.script``)."""
    return " ".join(text.replace("[", "").replace("]", "").split())


class _Checker:
    def __init__(self, tree: ast.Module, known: _Names) -> None:
        self.tree = tree
        self.known = known
        self.violations: list[Violation] = []
        self.lines: list[str] = []
        self.scene_class: str | None = None
        self.bound: set[str] = set()
        self.own_attributes: set[str] = set()

    def refuse(self, code: str, message: str, node: ast.AST | None = None) -> None:
        if len(self.violations) < MAX_VIOLATIONS:
            self.violations.append(Violation(code, message, getattr(node, "lineno", None)))

    # -- what the file binds ------------------------------------------------

    def bind(self, name: str, node: ast.AST) -> None:
        if name.startswith("_"):
            self.refuse("underscore", f"`{name}`: a name may not begin with an underscore.", node)
        elif name in MODULE_NAMES:
            self.refuse("module_name", f"`{name}` is the engine's name and stays as it is.", node)
        elif name in _PYTHON_NAMES and name not in ALLOWED_BUILTINS:
            self.refuse(
                "python_name", f"`{name}` is a name of Python's own. Use another name.", node
            )
        self.bound.add(name)

    def collect(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.bind(node.name, node)
            if isinstance(node, ast.ClassDef):
                # The scene's own methods are its own: `self.name(...)` calls them.
                self.own_attributes.update(
                    item.name
                    for item in node.body
                    if isinstance(item, ast.FunctionDef) and item.name != "construct"
                )
            if isinstance(node, (ast.FunctionDef, ast.Lambda)):
                arguments = node.args
                for argument in (
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                    *([arguments.vararg] if arguments.vararg else []),
                    *([arguments.kwarg] if arguments.kwarg else []),
                ):
                    self.bind(argument.arg, argument)
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                self.bind(node.id, node)
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Store)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
            ):
                self.own_attributes.add(node.attr)

    # -- the shape of the file ----------------------------------------------

    def shape(self) -> None:
        imported: set[str] = set()
        classes = [node for node in ast.walk(self.tree) if isinstance(node, ast.ClassDef)]
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in IMPORTS or alias.asname != IMPORTS[alias.name]:
                        self.refuse(
                            "import",
                            "Import only `import manimgx as m`, `import numpy as np` and "
                            "`import math`.",
                            node,
                        )
                    else:
                        imported.add(alias.name)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)) or (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            else:
                self.refuse(
                    "top_level",
                    "At the top of the file: imports, functions, the scene, and assignments.",
                    node,
                )
        for inner in ast.walk(self.tree):
            if isinstance(inner, ast.Import) and inner not in self.tree.body:
                self.refuse("import", "Imports go at the top of the file.", inner)
        if "manimgx" not in imported:
            self.refuse("import", "The file must begin with `import manimgx as m`.")
        if len(classes) != 1 or classes[0] not in self.tree.body:
            self.refuse(
                "one_scene",
                "The file must define exactly one class: the scene, `class Chapter(m.Scene)`.",
                classes[1] if len(classes) > 1 else None,
            )
            return
        scene = classes[0]
        base = scene.bases[0] if len(scene.bases) == 1 else None
        if (
            not isinstance(base, ast.Attribute)
            or not isinstance(base.value, ast.Name)
            or base.value.id != "m"
            or base.attr != "Scene"
            or scene.keywords
        ):
            self.refuse("scene_base", "The scene must be a plain `m.Scene`.", scene)
        self.scene_class = scene.name
        methods: set[str] = set()
        for item in scene.body:
            if isinstance(item, ast.FunctionDef):
                methods.add(item.name)
                if item.name != "construct" and item.name in self.known.scene:
                    self.refuse(
                        "scene_method",
                        f"`{item.name}` is the scene's own. Give your method another name.",
                        item,
                    )
            elif not (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and isinstance(item.value.value, str)
            ) and not isinstance(item, ast.Pass):
                self.refuse(
                    "scene_body",
                    "Inside the scene: methods only. Put constants at the top of the file.",
                    item,
                )
        if "construct" not in methods:
            self.refuse("construct", "The scene must define `construct(self)`.", scene)

    # -- every node ---------------------------------------------------------

    def walk(self) -> None:
        for node in ast.walk(self.tree):
            for kind, word in _REFUSED_NODES.items():
                if isinstance(node, kind):
                    self.refuse("construct_refused", f"`{word}` may not be used.", node)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.decorator_list:
                self.refuse("decorator", "Decorators may not be used.", node)
            if isinstance(node, ast.Name):
                self.name(node)
            elif isinstance(node, ast.Attribute):
                self.attribute(node)
            elif isinstance(node, ast.Call):
                self.call(node)
            elif isinstance(node, ast.Constant):
                self.constant(node)
            elif isinstance(node, ast.keyword) and node.arg and node.arg.startswith("_"):
                self.refuse("underscore", "A keyword may not begin with an underscore.", node)

    def name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Load):
            return
        name = node.id
        if name.startswith("_"):
            self.refuse("underscore", f"`{name}`: a name may not begin with an underscore.", node)
        elif name in MODULE_NAMES or name in ALLOWED_BUILTINS:
            return
        elif name in _PYTHON_NAMES:
            self.refuse("python_name", f"`{name}` may not be used in a film.", node)
        elif name not in self.bound:
            self.refuse("unknown_name", f"`{name}` is not defined in this file.", node)

    def attribute(self, node: ast.Attribute) -> None:
        attr = node.attr
        if attr.startswith("_"):
            self.refuse("underscore", f"`.{attr}`: nothing that begins with an underscore.", node)
            return
        owner = node.value.id if isinstance(node.value, ast.Name) else None
        if owner == "m":
            if attr not in self.known.api:
                self.refuse("api", f"`m.{attr}` is not something a film may use.", node)
        elif owner == "np":
            if attr not in NUMPY:
                self.refuse("numpy", f"`np.{attr}` is not something a film may use.", node)
        elif owner == "math":
            if attr not in MATH:
                self.refuse("math", f"`math.{attr}` does not exist.", node)
        elif owner == "self" and attr in self.own_attributes:
            if attr in self.known.scene or attr in self.known.refused:
                self.refuse(
                    "own_attribute",
                    f"`self.{attr}` is the engine's own name. Keep yours under another.",
                    node,
                )
        elif attr not in self.known.members and attr not in COMMON and attr not in _NUMPY_INNER:
            self.refuse("member", f"`.{attr}` is not something a film may use.", node)

    def call(self, node: ast.Call) -> None:
        function = node.func
        for keyword in node.keywords:
            if keyword.arg is None:
                self.refuse("splat", "`**` may not be used in a call: write each keyword.", node)
                continue
            if keyword.arg in _PLAIN_VALUE:
                value = keyword.value
                if not (
                    isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                    and _PLAIN_VALUE[keyword.arg].match(value.value)
                ):
                    self.refuse(
                        "keyword_value", f"`{keyword.arg}=` takes a plain name, written out.", node
                    )
            elif _WAY_OUT_KEYWORD.search(keyword.arg) and keyword.arg not in _PATHS_THAT_ARE_NOT:
                self.refuse("keyword", f"`{keyword.arg}=` may not be used in a film.", node)
        if not isinstance(function, ast.Attribute):
            return
        owner = function.value.id if isinstance(function.value, ast.Name) else None
        if owner == "m" and function.attr == "Code" and node.args:
            self.refuse(
                "code", "`m.Code` takes its code as `code_string=`, never by position.", node
            )
        if owner == "self" and function.attr == "say":
            self.say(node)

    def say(self, node: ast.Call) -> None:
        first = node.args[0] if node.args else None
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            self.refuse(
                "say",
                "`self.say` takes what is said as one plain string, written out in the call.",
                node,
            )
            return
        text = first.value.strip()
        problem = spoken_problem(text)
        if problem:
            self.refuse("say", f"A line that is said {problem}.", node)
            return
        # The engine plays one animation in each bracketed span, in order, and stops on a
        # line that has a different number of each: said here for every such line at once.
        spans = text.count("[")
        animations = node.args[1:]
        if (
            spans
            and not any(isinstance(item, ast.Starred) for item in animations)
            and spans != len(animations)
        ):
            self.refuse(
                "say",
                f"This line has {spans} bracketed span{'s' if spans != 1 else ''} and "
                f"{len(animations)} animation{'s' if len(animations) != 1 else ''}: give one "
                "animation for each span, in the same order.",
                node,
            )
            return
        if len(self.lines) >= MAX_LINES:
            self.refuse("say", f"A chapter says at most {MAX_LINES} lines.", node)
            return
        self.lines.append(text)

    def constant(self, node: ast.Constant) -> None:
        value = node.value
        if isinstance(value, bytes):
            self.refuse("bytes", "Bytes may not be used.", node)
            return
        if not isinstance(value, str):
            return
        problem = text_problem(value)
        if problem is not None:
            self.refuse(problem.code, problem.message, node)


def text_problem(value: str) -> Violation | None:
    """Why a chapter may not hold this string, or nothing: Adle's own chapters, which put
    a course's words on the stage, ask this of each before they hold it."""
    if len(value) > MAX_STRING_CHARS:
        return Violation("string", "A string is too long.")
    if _URL_LIKE.search(value):
        return Violation("link", "A string holds an address. A film refers to none.")
    if _PATH_LIKE.search(value):
        return Violation("path", "A string holds a file path. A film reads no files.")
    if _TYPESETTER_OUT.search(value):
        return Violation("typesetter", "A string holds a command that reads or writes a file.")
    if _CONTROL.search(value.replace("\n", " ").replace("\t", " ")):
        return Violation("characters", "A string holds characters that are not text.")
    if (
        value.isidentifier()
        and _WAY_OUT_KEYWORD.search(value)
        and value not in _PATHS_THAT_ARE_NOT
        and "_" in value
    ):
        return Violation("option_name", f"`{value}` names an option a film may not set.")
    return None


def spoken_problem(text: str) -> str | None:
    """Why a line cannot be said as it is written, or nothing."""
    if not text or not said(text).strip():
        return "is empty"
    if len(text) > MAX_LINE_CHARS:
        return f"is longer than {MAX_LINE_CHARS} characters: say it in two"
    if _CONTROL.search(text) or "\n" in text:
        return "must be one line of plain words"
    if "$" in text or "\\" in text:
        return "is read aloud: write mathematics in words, not notation"
    if _URL_LIKE.search(text) or _MARKUP.search(text):
        return "must be plain words"
    depth = 0
    for character in text:
        if character == "[":
            depth += 1
            if depth > 1:
                return "has a bracket inside a bracket"
        elif character == "]":
            depth -= 1
            if depth < 0:
                return "closes a bracket it did not open"
    if depth:
        return "opens a bracket it does not close"
    if "[]" in text.replace(" ", ""):
        return "has brackets around nothing"
    return None


def with_engine_names(source: str) -> str:
    """A chapter with the engine's names it used bare written as the engine's: ``WHITE`` as
    ``m.WHITE``, ``Circle(...)`` as ``m.Circle(...)``.

    A slip, mended here rather than sent back to be written again (as for a lesson,
    ADR-047): only a name the file never defines anywhere, that is not Python's own, and
    that the engine has and a chapter may use, in a file that imports the engine as ``m``.
    ``np`` or ``math`` used and not imported is imported, under that name. Nothing else
    is touched; the file is checked afterwards as any other.
    """
    normal = normalise_source(source)
    try:
        tree = ast.parse(normal)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return normal
    engine_import = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.Import)
            and any(alias.name == "manimgx" and alias.asname == "m" for alias in node.names)
        ),
        None,
    )
    if engine_import is None:
        return normal
    known = names()
    checker = _Checker(tree, known)
    imported = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    try:
        checker.collect()
        used = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        spots = sorted(
            (
                (node.lineno, node.col_offset, node.id)
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in known.api
                and node.id not in checker.bound
                and node.id not in MODULE_NAMES
                and node.id not in _PYTHON_NAMES
            ),
            reverse=True,
        )
    except RecursionError:
        return normal
    missing = [
        statement
        for name, statement in (("np", "import numpy as np"), ("math", "import math"))
        if name in used and name not in imported and name not in checker.bound
    ]
    if not spots and not missing:
        return normal
    lines = normal.split("\n")
    for line, column, name in spots:
        # Where a name is, Python says in bytes of the line.
        raw = lines[line - 1].encode("utf-8")
        if raw[column : column + len(name)] == name.encode("utf-8"):
            lines[line - 1] = (raw[:column] + b"m." + raw[column:]).decode("utf-8")
    after = engine_import.end_lineno or engine_import.lineno
    lines[after:after] = missing
    return "\n".join(lines)


def _unbracketed_after(text: str, kept: int) -> str:
    """A line with its first ``kept`` bracketed spans as they are and the brackets of the
    rest taken away."""
    out: list[str] = []
    seen = 0
    inside = False
    for character in text:
        if character == "[":
            seen += 1
            inside = seen <= kept
            if not inside:
                continue
        elif character == "]":
            if not inside:
                continue
            inside = False
        out.append(character)
    return "".join(out)


def with_spans_fitted(source: str) -> str:
    """A chapter whose lines have no more bracketed spans than animations.

    The engine plays one animation in each span, in order, and stops on a line with more
    spans than it has animations. Every chapter of the films made by hand had such a line
    (2026-11-25), so it is mended, not sent back: the spans after the last animation lose
    their brackets. The words, and how they are said, are the same, and each animation still
    plays in a span of its own. A line with fewer spans than animations is left to be
    refused: which words an animation belongs to is not Adle's to guess.
    """
    normal = normalise_source(source)
    try:
        tree = ast.parse(normal)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return normal
    edits: list[tuple[int, int, int, int, str]] = []
    for call in calls:
        function = call.func
        if not (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "self"
            and function.attr == "say"
            and call.args
        ):
            continue
        first, animations = call.args[0], call.args[1:]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if any(isinstance(item, ast.Starred) for item in animations):
            continue
        text = first.value
        spans = text.count("[")
        if spans <= len(animations) or spoken_problem(text.strip()) is not None:
            continue
        if first.end_lineno is None or first.end_col_offset is None:
            continue
        fitted = _unbracketed_after(text, len(animations))
        edits.append(
            (first.lineno, first.col_offset, first.end_lineno, first.end_col_offset, repr(fitted))
        )
    if not edits:
        return normal
    lines = [line.encode("utf-8") for line in normal.split("\n")]
    for start_line, start, end_line, end, literal in sorted(edits, reverse=True):
        # Where a literal is, Python says in bytes of its lines.
        head = lines[start_line - 1][:start]
        tail = lines[end_line - 1][end:]
        lines[start_line - 1 : end_line] = [head + literal.encode("utf-8") + tail]
    return "\n".join(line.decode("utf-8") for line in lines)


def check_chapter_source(source: str) -> ChapterReport:
    """Whether a chapter's file may be run by the film engine, without running any of it."""
    normal = normalise_source(source)
    digest = hashlib.sha256(normal.encode("utf-8")).hexdigest()

    def refused(*violations: Violation) -> ChapterReport:
        return ChapterReport(False, tuple(violations), None, (), digest)

    if len(normal) > MAX_SOURCE_CHARS:
        return refused(Violation("too_long", "The file is too long for one chapter."))
    if _CONTROL.search(normal.replace("\t", " ")):
        return refused(Violation("characters", "The file holds characters that are not text."))
    try:
        tree = ast.parse(normal)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as error:
        line = getattr(error, "lineno", None)
        return refused(Violation("syntax", "The file is not valid Python.", line))
    try:
        count = sum(1 for _ in ast.walk(tree))
    except RecursionError:
        return refused(Violation("too_deep", "The file is nested too deeply."))
    if count > MAX_AST_NODES:
        return refused(Violation("too_long", "The file is too long for one chapter."))
    checker = _Checker(tree, names())
    try:
        checker.collect()
        checker.shape()
        checker.walk()
    except RecursionError:
        return refused(Violation("too_deep", "The file is nested too deeply."))
    return ChapterReport(
        ok=not checker.violations,
        violations=tuple(checker.violations),
        scene_class=checker.scene_class,
        lines=tuple(checker.lines),
        content_hash=digest,
    )
