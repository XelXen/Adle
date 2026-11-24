"""Static safety policy for scene source files.

A scene is a Python file that Wanim compiles to JavaScript and runs in the
player. It is untrusted: it may have been written by a model that was shown
untrusted course material. This module decides, without executing anything,
whether a source file is acceptable to store and hand to the player.

What it enforces
----------------
* The file is valid CPython syntax. That alone rejects RapydScript-only escape
  hatches such as the raw-JavaScript literal ``v'...'``.
* Imports come only from the modules Wanim provides.
* Every name resolves to something the file defines, an allowlisted builtin, or
  the manim API of the pinned Wanim version (``data/wanim_names.json``). Because
  undeclared names would otherwise fall through to browser globals, this is what
  keeps ``window``, ``document``, ``fetch`` and friends out of reach. Scoping is
  resolved with :mod:`symtable`, so ``self`` outside a method is not accepted.
* Attribute and string-key access to JavaScript/DOM escape routes is refused.
* The file defines a supported scene class and follows Adle's conventions
  (event vocabulary, named controls, no ``__init__`` override).

What it is not
--------------
A sandbox. A determined author can compute an attribute name at run time. The
security boundary is the isolated player frame (see SECURITY.md); this policy
is defence in depth and a quality gate for generated code.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import symtable
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Final

MAX_SOURCE_CHARS: Final = 40_000
MAX_AST_NODES: Final = 6_000
MAX_SCENE_CLASSES: Final = 3

ALLOWED_MODULES: Final = frozenset({"manim", "numpy", "math", "random", "itertools"})

#: Python builtins a scene may use. Deliberately excludes anything reflective
#: (getattr, setattr, type, vars, globals, eval, exec, compile, __import__)
#: and anything that touches the outside world (open, input, print-to-file).
ALLOWED_BUILTINS: Final = frozenset(
    {
        "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float",
        "int", "isinstance", "iter", "len", "list", "map", "max", "min", "next", "pow",
        "print", "range", "reversed", "round", "set", "sorted", "str", "sum", "super",
        "tuple", "zip",
        "Exception", "ArithmeticError", "IndexError", "KeyError", "StopIteration",
        "TypeError", "ValueError", "ZeroDivisionError",
        # `from manim import *` exposes numpy as `np`, as upstream manim does.
        "np",
    }
)  # fmt: skip

#: Scene base classes exercised by Adle's end-to-end tests.
SUPPORTED_SCENE_BASES: Final = frozenset({"Scene", "InteractiveScene"})
#: Bases that exist in Wanim but are untested here; refused until they are.
UNSUPPORTED_SCENE_BASES: Final = frozenset(
    {
        "ThreeDScene", "SpecialThreeDScene", "MovingCameraScene", "ZoomedScene",
        "VectorScene", "LinearTransformationScene", "InteractiveThreeDScene",
        "InteractiveLinearTransformationScene",
    }
)  # fmt: skip

#: The closed event vocabulary. Must match `SCENE_EVENT_NAMES` in
#: packages/event-protocol (checked by tests/unit/test_scene_policy.py).
EVENT_NAMES: Final = ("passed", "explored", "progress", "step", "layout")

#: Attribute (and constant subscript) names that lead out of the Python-like
#: world into JavaScript objects, the DOM, or the renderer's canvas.
FORBIDDEN_ATTRIBUTES: Final = frozenset(
    {
        "constructor", "prototype", "__proto__", "caller", "callee", "apply", "bind", "call",
        "renderer", "ctx", "canvas", "ownerDocument", "defaultView", "contentWindow",
        "contentDocument", "parentNode", "parentElement", "getRootNode", "host",
        "message_sink", "window", "document", "globalThis", "eval", "postMessage",
    }
)  # fmt: skip

#: Names that must never be bound in a scene, so a local definition can never be
#: used to smuggle a same-named browser global past the name check.
RESERVED_NAMES: Final = frozenset(
    {
        "window", "document", "globalThis", "top", "parent", "frames", "opener", "location",
        "navigator", "history", "fetch", "XMLHttpRequest", "WebSocket", "EventSource",
        "Worker", "SharedWorker", "localStorage", "sessionStorage", "indexedDB", "caches",
        "eval", "Function", "setTimeout", "setInterval", "requestAnimationFrame",
        "queueMicrotask", "postMessage", "importScripts", "require", "process", "Reflect",
        "Proxy", "Object", "Symbol", "Promise", "console", "alert",
    }
)  # fmt: skip

_CONTROL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_URL_LIKE = re.compile(
    r"(?i)(?:https?|wss?|ftp|file)://|\b(?:javascript|vbscript|blob):|\bdata:[a-z]+/"
)


def names_a_link(text: str) -> bool:
    """Whether a piece of text holds what the policy refuses in any string of a scene: an
    address, or the beginning of one. Whoever writes a scene from data asks first, so that
    one such string costs the picture that string and not the whole of it."""
    return _URL_LIKE.search(text) is not None


_FORBIDDEN_NODES: Final = (
    ast.AsyncFunctionDef,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.Await,
)


@dataclass(frozen=True, slots=True)
class PolicyViolation:
    """One reason a scene was rejected. ``code`` is stable; ``message`` is for people."""

    code: str
    message: str
    line: int | None = None


@dataclass(frozen=True, slots=True)
class SceneReport:
    """The outcome of checking one scene source file."""

    ok: bool
    violations: tuple[PolicyViolation, ...]
    #: Scene classes found, in source order.
    scene_classes: tuple[str, ...] = ()
    #: True when the first scene class has an interactive ``blueprint()`` page.
    interactive: bool = False
    #: Names registered in ``self.adle_controls``.
    controls: tuple[str, ...] = ()
    #: Event names the scene may report.
    events: tuple[str, ...] = ()
    #: How many steps it is paced in (ADR-049): the steps it reports as each ends,
    #: ``post_message("step", n)`` for each n from 0. None that are numbered so: 0.
    steps: int = 0
    #: SHA-256 of the normalised source; the identity of the stored artifact.
    content_hash: str = ""
    wanim_version: str = ""


@dataclass(slots=True)
class _Names:
    wanim_version: str
    manim: frozenset[str]
    stdlib: dict[str, frozenset[str]] = field(default_factory=dict)


@lru_cache(maxsize=1)
def _names() -> _Names:
    raw = json.loads(
        resources.files("adle_core.generation.data")
        .joinpath("wanim_names.json")
        .read_text(encoding="utf-8")
    )
    return _Names(
        wanim_version=raw["wanim_version"],
        manim=frozenset(raw["manim"]),
        stdlib={module: frozenset(raw[module]) for module in ("math", "random", "itertools")},
    )


def pinned_wanim_version() -> str:
    """The Wanim version the name allowlist was generated from."""
    return _names().wanim_version


def normalise_source(source: str) -> str:
    """Canonical text for hashing and storage.

    LF newlines, no trailing spaces, exactly one final newline.
    """
    lines = [line.rstrip() for line in source.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip("\n") + "\n"


def content_hash(source: str) -> str:
    return hashlib.sha256(normalise_source(source).encode("utf-8")).hexdigest()


#: Methods that must be given their arguments in order, without names, and how to write
#: each. Seen in Wanim 0.1.3 on 2026-11-21 (`e2e/scene-player.spec.ts` reads the pixels).
IN_ORDER_ONLY = {
    "set_fill": (
        "mobject.set_fill(self.blue, 0.3), or mobject.set_fill(None, 0.3) to keep the color it has"
    ),
    "set_color": "mobject.set_color(self.blue)",
}


#: Calls that stop a scene in the pinned runtime however they are given, and what to use.
_BROKEN_CALLS = {
    "Ellipse": (
        "Ellipse stops the scene in this runtime. Draw a circle and stretch it: "
        "Circle(radius=1).stretch_to_fit_width(w).stretch_to_fit_height(h)."
    ),
    "Flash": (
        "Flash stops the scene in this runtime. Point with Indicate(...), or draw a "
        "SurroundingRectangle with Create."
    ),
}


class _Checker:
    def __init__(self, source: str) -> None:
        self.source = source
        self.violations: list[PolicyViolation] = []
        self.star_modules: set[str] = set()
        self.scene_classes: list[ast.ClassDef] = []
        self.controls: list[str] = []
        self.events: list[str] = []
        self.steps: set[int] = set()
        self._first_use: dict[str, int] = {}

    def fail(self, code: str, message: str, node: ast.AST | None = None) -> None:
        line = getattr(node, "lineno", None) if node is not None else None
        self.violations.append(PolicyViolation(code, message, line))

    # -- syntax tree -------------------------------------------------------

    def check_tree(self, tree: ast.Module) -> None:
        node_count = 0
        for node in ast.walk(tree):
            node_count += 1
            if isinstance(node, _FORBIDDEN_NODES):
                self.fail(
                    "unsupported_syntax", "Asynchronous code is not supported in scenes.", node
                )
            elif isinstance(node, ast.Import):
                self._check_import(node)
            elif isinstance(node, ast.ImportFrom):
                self._check_import_from(node)
            elif isinstance(node, ast.Attribute):
                self._check_attribute_name(node.attr, node)
            elif isinstance(node, ast.Subscript):
                key = node.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    self._check_attribute_name(key.value, node)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if _URL_LIKE.search(node.value):
                    self.fail(
                        "url_in_string",
                        "Scenes cannot reference URLs or external resources.",
                        node,
                    )
            elif isinstance(node, ast.FunctionDef | ast.ClassDef):
                self._check_definition(node)
            elif isinstance(node, ast.Call):
                self._check_call(node)
            elif isinstance(node, ast.Assign):
                self._collect_controls(node)
            elif isinstance(node, ast.While):
                self._check_loop(node)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                self._first_use.setdefault(node.id, node.lineno)

        if node_count > MAX_AST_NODES:
            self.fail(
                "too_complex",
                "The scene is too large. Keep one focused idea per scene.",
            )
        self._check_scene_classes()

    def _check_import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root not in ALLOWED_MODULES:
                self.fail(
                    "forbidden_import",
                    f"Module '{alias.name}' is not available. "
                    f"Scenes may import only: {', '.join(sorted(ALLOWED_MODULES))}.",
                    node,
                )

    def _check_import_from(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        root = module.split(".")[0]
        if node.level != 0 or root not in ALLOWED_MODULES:
            self.fail(
                "forbidden_import",
                f"Module '{module or '.'}' is not available. "
                f"Scenes may import only: {', '.join(sorted(ALLOWED_MODULES))}.",
                node,
            )
            return
        names = _names()
        for alias in node.names:
            if alias.name == "*":
                self.star_modules.add(root)
                continue
            if alias.name.startswith("_"):
                self.fail("forbidden_import", f"'{alias.name}' is a private name.", node)
            elif root == "manim" and alias.name not in names.manim:
                self.fail(
                    "forbidden_import",
                    f"'{alias.name}' is not part of the supported manim API.",
                    node,
                )
            elif root in names.stdlib and alias.name not in names.stdlib[root]:
                self.fail("forbidden_import", f"'{alias.name}' is not provided by '{root}'.", node)

    def _check_attribute_name(self, name: str, node: ast.AST) -> None:
        if name in FORBIDDEN_ATTRIBUTES or (name.startswith("__") and name.endswith("__")):
            self.fail(
                "forbidden_attribute",
                f"Access to '{name}' is not allowed in a scene.",
                node,
            )

    def _check_definition(self, node: ast.FunctionDef | ast.ClassDef) -> None:
        if node.decorator_list:
            self.fail("unsupported_syntax", "Decorators are not supported in scenes.", node)
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith("__") and node.name.endswith("__"):
                code = "init_override" if node.name == "__init__" else "unsupported_syntax"
                message = (
                    "Never override __init__ in a scene. Use setup(), blueprint(), or construct()."
                    if node.name == "__init__"
                    else f"Special method '{node.name}' is not supported in scenes."
                )
                self.fail(code, message, node)
            return

        bases = [base.id for base in node.bases if isinstance(base, ast.Name)]
        unsupported = [base for base in bases if base in UNSUPPORTED_SCENE_BASES]
        if unsupported:
            self.fail(
                "unsupported_scene_base",
                f"'{unsupported[0]}' scenes are not supported. Use Scene or InteractiveScene.",
                node,
            )
        elif any(base in SUPPORTED_SCENE_BASES for base in bases):
            self.scene_classes.append(node)

    def _check_call(self, node: ast.Call) -> None:
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr in IN_ORDER_ONLY:
            if node.keywords or not node.args:
                # Observed in the pinned runtime. Called with names only, these take the
                # names for the colour and fail when the scene runs. With the colour in
                # place and the rest by name, set_fill runs and the fill is gone. A lesson
                # a real model wrote lost its interactive picture to the first of these.
                self.fail(
                    "unreliable_call",
                    f"Give {function.attr} its arguments in order, without names: "
                    f"{IN_ORDER_ONLY[function.attr]}.",
                    node,
                )
            return
        if isinstance(function, ast.Name) and function.id == "Circumscribe":
            # Observed in the pinned runtime, 2026-11-21: given a colour by name, it takes the
            # name for its shape and stops the scene ("shape should be either Rectangle or
            # Circle"); without one it runs, in a yellow that is not in the palette.
            self.fail(
                "unreliable_call",
                "Circumscribe stops the scene in this runtime when it is given a color, and "
                "without one draws outside the palette. Point with Indicate(...), or draw a "
                "SurroundingRectangle with Create and take it away with FadeOut.",
                node,
            )
            return
        if (
            isinstance(function, ast.Name)
            and function.id == "Indicate"
            and any(key.arg in ("color", "colour") for key in node.keywords)
        ):
            # Observed in the pinned runtime, 2026-11-22: given a colour, Indicate makes a
            # point that is not a number, and the scene stops ("non-finite point/vector
            # value"). Without one it runs.
            self.fail(
                "unreliable_call",
                "Indicate stops the scene in this runtime when it is given a color. Call "
                "Indicate(...) without one, or draw a SurroundingRectangle with Create.",
                node,
            )
            return
        if isinstance(function, ast.Name) and function.id in _BROKEN_CALLS:
            # Observed in the pinned runtime, 2026-11-22 (ADR-049): each stops the scene
            # with "non-finite point/vector value" as soon as it is drawn.
            self.fail("unreliable_call", _BROKEN_CALLS[function.id], node)
            return
        if isinstance(function, ast.Name) and function.id == "Dot":
            positioned = bool(node.args) or any(key.arg == "point" for key in node.keywords)
            if positioned:
                # Observed in the pinned runtime: a Dot given its position as an argument
                # loses its colour and is drawn white, which cannot be seen on the light
                # stage. Nothing fails, so it has to be caught here.
                self.fail(
                    "unreliable_call",
                    "Create a Dot with keywords only and place it with move_to: "
                    "Dot(color=..., radius=...).move_to(point).",
                    node,
                )
            return
        if not (isinstance(function, ast.Attribute) and function.attr == "post_message"):
            return
        if not node.args:
            self.fail("invalid_event", "post_message needs an event name.", node)
            return
        name = node.args[0]
        if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
            self.fail(
                "invalid_event",
                "The event name passed to post_message must be a string literal.",
                node,
            )
        elif name.value not in EVENT_NAMES:
            self.fail(
                "invalid_event",
                f"Unknown event '{name.value}'. Allowed events: {', '.join(EVENT_NAMES)}.",
                node,
            )
        else:
            if name.value not in self.events:
                self.events.append(name.value)
            if name.value == "step" and len(node.args) > 1:
                number = node.args[1]
                if (
                    isinstance(number, ast.Constant)
                    and type(number.value) is int
                    and 0 <= number.value < 64
                ):
                    self.steps.add(number.value)

    def _collect_controls(self, node: ast.Assign) -> None:
        for target in node.targets:
            if not (isinstance(target, ast.Attribute) and target.attr == "adle_controls"):
                continue
            if not isinstance(node.value, ast.Dict):
                self.fail(
                    "invalid_controls",
                    "adle_controls must be a dict literal of name -> control.",
                    node,
                )
                continue
            for key in node.value.keys:
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and _CONTROL_NAME.match(key.value)
                ):
                    if key.value not in self.controls:
                        self.controls.append(key.value)
                else:
                    self.fail(
                        "invalid_controls",
                        "adle_controls keys must be short identifier-like string literals.",
                        node,
                    )

    def _check_loop(self, node: ast.While) -> None:
        """Reject the obvious never-yielding loop; the player watchdog handles the rest."""
        always = isinstance(node.test, ast.Constant) and bool(node.test.value)
        if not always:
            return
        for inner in ast.walk(node):
            if isinstance(inner, ast.Break | ast.Return | ast.Raise):
                return
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Attribute)
                and inner.func.attr in {"wait", "play", "next_slide"}
            ):
                return
        self.fail(
            "unbounded_loop",
            "This loop never ends and never lets the scene draw a frame.",
            node,
        )

    def _check_scene_classes(self) -> None:
        if not self.scene_classes:
            self.fail(
                "no_scene",
                "The file must define a class that subclasses Scene or InteractiveScene.",
            )
            return
        if len(self.scene_classes) > MAX_SCENE_CLASSES:
            self.fail("too_complex", "Use one scene class per file.", self.scene_classes[-1])
        for scene in self.scene_classes:
            methods = {item.name for item in scene.body if isinstance(item, ast.FunctionDef)}
            if not methods & {"construct", "blueprint", "setup"}:
                self.fail(
                    "no_scene",
                    f"Scene '{scene.name}' needs a construct() or blueprint() method.",
                    scene,
                )

    # -- name resolution ---------------------------------------------------

    def check_names(self) -> None:
        try:
            table = symtable.symtable(self.source, "scene.py", "exec")
        except SyntaxError:
            return  # Already reported by the parser.

        names = _names()
        module_defined = {
            symbol.get_name()
            for symbol in table.get_symbols()
            if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
        }
        allowed = set(module_defined) | ALLOWED_BUILTINS
        if "manim" in self.star_modules:
            allowed |= names.manim
        for module in self.star_modules & names.stdlib.keys():
            allowed |= names.stdlib[module]

        self._visit_scope(table, allowed, unknown=set(), reserved=set(), is_module=True)

    def _visit_scope(
        self,
        scope: symtable.SymbolTable,
        allowed: set[str],
        *,
        unknown: set[str],
        reserved: set[str],
        is_module: bool,
    ) -> None:
        for symbol in scope.get_symbols():
            name = symbol.get_name()
            binds = symbol.is_assigned() or symbol.is_imported() or symbol.is_parameter()
            if binds and name in RESERVED_NAMES and name not in reserved:
                reserved.add(name)
                self.fail(
                    "reserved_name",
                    f"'{name}' is reserved and cannot be defined in a scene.",
                )
            if not symbol.is_referenced() or name in unknown:
                continue
            if is_module:
                resolved_here = symbol.is_assigned() or symbol.is_imported()
            else:
                resolved_here = (
                    symbol.is_parameter()
                    or symbol.is_free()
                    or (symbol.is_local() and not symbol.is_global())
                )
            if not resolved_here and name not in allowed:
                unknown.add(name)
                self.violations.append(
                    PolicyViolation(
                        "unknown_name",
                        f"'{name}' is not defined in this file and is not part of the manim API.",
                        self._first_use.get(name),
                    )
                )
        for child in scope.get_children():
            self._visit_scope(child, allowed, unknown=unknown, reserved=reserved, is_module=False)


def check_scene_source(source: object) -> SceneReport:
    """Decide whether ``source`` is an acceptable scene file. Never raises on bad input."""
    version = pinned_wanim_version()
    if not isinstance(source, str) or not source.strip():
        violation = PolicyViolation("empty", "The scene file is empty.")
        return SceneReport(ok=False, violations=(violation,), wanim_version=version)
    if len(source) > MAX_SOURCE_CHARS:
        violation = PolicyViolation(
            "too_large",
            f"The scene file is larger than {MAX_SOURCE_CHARS} characters.",
        )
        return SceneReport(ok=False, violations=(violation,), wanim_version=version)
    if "\x00" in source:
        violation = PolicyViolation("syntax_error", "The scene file contains a NUL byte.")
        return SceneReport(ok=False, violations=(violation,), wanim_version=version)

    try:
        tree = ast.parse(source, filename="scene.py", mode="exec")
    except (SyntaxError, ValueError, RecursionError, MemoryError) as error:
        reason = getattr(error, "msg", None) or type(error).__name__
        violation = PolicyViolation(
            "syntax_error",
            f"The scene is not valid Python: {reason}.",
            getattr(error, "lineno", None),
        )
        return SceneReport(ok=False, violations=(violation,), wanim_version=version)

    checker = _Checker(source)
    try:
        checker.check_tree(tree)
        checker.check_names()
    except (RecursionError, MemoryError):
        # Nested deeper than a scene has any reason to be. What could not be looked at
        # all the way down is not let through.
        violation = PolicyViolation("too_large", "The scene is nested too deeply to check.")
        return SceneReport(ok=False, violations=(violation,), wanim_version=version)

    first = checker.scene_classes[0] if checker.scene_classes else None
    interactive = first is not None and any(
        isinstance(item, ast.FunctionDef) and item.name == "blueprint" for item in first.body
    )
    return SceneReport(
        ok=not checker.violations,
        violations=tuple(checker.violations),
        scene_classes=tuple(scene.name for scene in checker.scene_classes),
        interactive=interactive,
        controls=tuple(checker.controls),
        events=tuple(checker.events),
        steps=len(checker.steps) if checker.steps == set(range(len(checker.steps))) else 0,
        content_hash=content_hash(source),
        wanim_version=version,
    )
