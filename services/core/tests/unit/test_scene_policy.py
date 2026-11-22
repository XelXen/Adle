"""The static scene policy: what generated scene code may and may not contain."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

from adle_core.generation.scene_policy import (
    EVENT_NAMES,
    MAX_SOURCE_CHARS,
    SceneReport,
    check_scene_source,
    content_hash,
    normalise_source,
    pinned_wanim_version,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLES = REPO_ROOT / "skills" / "wanim-scene-authoring" / "examples"
HOSTILE = REPO_ROOT / "apps" / "desktop" / "e2e" / "fixtures" / "scenes"
BUNDLED = [
    REPO_ROOT
    / "apps"
    / "desktop"
    / "renderer"
    / "src"
    / "screens"
    / "settings"
    / "runtime-check.py",
]


def scene(body: str, *, base: str = "Scene", method: str = "construct") -> str:
    """Wrap statements in a minimal valid scene."""
    indented = textwrap.indent(textwrap.dedent(body).strip("\n"), " " * 8)
    return f"from manim import *\n\n\nclass Demo({base}):\n    def {method}(self):\n{indented}\n"


def codes(report: SceneReport) -> set[str]:
    return {violation.code for violation in report.violations}


# -- what must be accepted -------------------------------------------------


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.py")) + BUNDLED, ids=lambda p: p.name)
def test_every_shipped_scene_passes(path: Path) -> None:
    report = check_scene_source(path.read_text(encoding="utf-8"))
    assert report.violations == ()
    assert report.ok
    assert report.scene_classes
    assert report.wanim_version == pinned_wanim_version()


def test_there_are_examples_to_check() -> None:
    assert len(list(EXAMPLES.glob("*.py"))) >= 3


def test_report_describes_an_interactive_scene() -> None:
    report = check_scene_source((EXAMPLES / "neuron_weight.py").read_text(encoding="utf-8"))
    assert report.scene_classes == ("NeuronWeight",)
    assert report.interactive is True
    assert report.controls == ("weight", "bias_on")
    assert report.events == ("explored", "passed")
    assert re.fullmatch(r"[0-9a-f]{64}", report.content_hash)


def test_report_describes_an_animation_only_scene() -> None:
    report = check_scene_source((EXAMPLES / "weighted_sum.py").read_text(encoding="utf-8"))
    assert report.interactive is False
    assert report.controls == ()
    assert report.events == ()


@pytest.mark.parametrize(
    "body",
    [
        "self.play(Create(Circle(radius=1, color=BLUE)), run_time=0.5)",
        "values = [x * 2 for x in range(5)]\nself.add(Text(str(sum(values))))",
        "group = VGroup(*[Dot() for _ in range(3)]).arrange(RIGHT, buff=0.3)\nself.add(group)",
        "tracker = ValueTracker(0)\nself.play(tracker.animate.set_value(1))",
        "def helper(a, b=2):\n    return max(a, b)\nself.wait(helper(0.1))",
        "points = np.array([[0, 0, 0], [1, 1, 0]])\nself.add(Line(points[0], points[1]))",
        "try:\n    self.wait(0.1)\nexcept ValueError as error:\n    print(error)",
        'label = Text(f"z = {round(1.234, 2)}")\nself.add(label)',
        "count = 0\nwhile True:\n    count += 1\n    self.wait(0.1)\n    if count > 2:\n        break",
    ],
)
def test_ordinary_manim_code_is_accepted(body: str) -> None:
    report = check_scene_source(scene(body))
    assert report.violations == ()


def test_allowed_standard_library_imports() -> None:
    source = (
        "import math\nimport random\nimport itertools\nimport numpy as np\n"
        "from math import sin, pi\nfrom numpy import cos\n"
        + scene("self.wait(sin(pi) + cos(0) + math.sqrt(4) + random.random())")
    )
    assert check_scene_source(source).ok


# -- what must be rejected -------------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("syntax_error.py", "syntax_error"),
        ("verbatim_js.py", "syntax_error"),  # v'...' is RapydScript, not Python
        ("bad_import.py", "forbidden_import"),
        ("no_scene.py", "no_scene"),
        ("busy_loop.py", "unbounded_loop"),
        ("runtime_error.py", "unknown_name"),
        ("hostile_probe.py", "unknown_name"),
        # Run, these two go wrong in the pinned runtime: one leaves a shape empty, one stops.
        ("fill_by_name.py", "unreliable_call"),
        ("fill_without_colour.py", "unreliable_call"),
        # And this one stops whatever it is given.
        ("circumscribe.py", "unreliable_call"),
        ("indicate_colour.py", "unreliable_call"),
    ],
)
def test_broken_and_hostile_fixtures_are_rejected(fixture: str, expected: str) -> None:
    report = check_scene_source((HOSTILE / fixture).read_text(encoding="utf-8"))
    assert not report.ok
    assert expected in codes(report)


def test_hostile_probe_is_rejected_for_every_browser_global_it_touches() -> None:
    report = check_scene_source((HOSTILE / "hostile_probe.py").read_text(encoding="utf-8"))
    unknown = {v.message.split("'")[1] for v in report.violations if v.code == "unknown_name"}
    assert {"window", "fetch", "require"} <= unknown


@pytest.mark.parametrize(
    "name",
    ["window", "document", "globalThis", "fetch", "XMLHttpRequest", "localStorage", "eval",
     "Function", "setTimeout", "navigator", "parent", "top", "console", "require", "process",
     "getattr", "setattr", "exec", "open", "__import__", "globals", "vars", "type", "compile"],
)  # fmt: skip
def test_browser_globals_and_reflective_builtins_are_unknown_names(name: str) -> None:
    report = check_scene_source(scene(f"x = {name}\nself.wait(0.1)"))
    assert "unknown_name" in codes(report)


def test_self_outside_a_method_is_the_browser_window_and_is_rejected() -> None:
    # In JavaScript a bare `self` is the window object. It is only safe as a parameter.
    source = (
        "from manim import *\n\nleak = self.parent\n\n" + scene("self.wait(0.1)").split("\n\n\n")[1]
    )
    report = check_scene_source(source)
    assert "unknown_name" in codes(report)
    assert any("'self'" in violation.message for violation in report.violations)


def test_a_local_definition_cannot_launder_a_browser_global() -> None:
    source = scene(
        """
        def decoy():
            fetch = 1
            return fetch
        fetch("adle://app/index.html")
        """
    )
    report = check_scene_source(source)
    # Binding a reserved name is refused, and the outer use is still unresolved.
    assert {"reserved_name", "unknown_name"} <= codes(report)


@pytest.mark.parametrize(
    "body",
    [
        "x = (lambda: 0).constructor('return 1')()",
        "x = self.renderer.ctx.canvas.ownerDocument.defaultView",
        "x = ''.__class__",
        "x = [].__proto__",
        "x = self.camera['constructor']",
        "x = {}['__proto__']",
        "f = max.bind(None)",
        "self.message_sink('x', 1)",
    ],
)
def test_escape_route_attributes_are_rejected(body: str) -> None:
    assert "forbidden_attribute" in codes(check_scene_source(scene(body)))


@pytest.mark.parametrize(
    "statement",
    [
        "import os",
        "import sys, subprocess",
        "from pathlib import Path",
        "import numpy.ctypeslib as leak\nimport socket",
        "from . import sibling",
        "from manim import _config",
        "from manim import configure_fonts",
        "from manim import ImageMobject",
        "from math import not_a_real_function",
    ],
)
def test_forbidden_imports(statement: str) -> None:
    report = check_scene_source(statement + "\n" + scene("self.wait(0.1)"))
    assert "forbidden_import" in codes(report)


def test_plumbing_and_asset_classes_are_not_part_of_the_scene_api() -> None:
    for name in ("render_presentation_to_canvas", "configure_fonts", "ImageMobject", "SVGMobject",
                 "open_file", "DomInteractiveHost", "build_embed_hash", "config"):  # fmt: skip
        report = check_scene_source(scene(f"x = {name}\nself.wait(0.1)"))
        assert "unknown_name" in codes(report), name


def test_names_require_the_star_import() -> None:
    source = "class Demo(Scene):\n    def construct(self):\n        self.add(Circle())\n"
    assert "unknown_name" in codes(check_scene_source(source))


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ('self.add(Text("see https://example.com/x"))', "url_in_string"),
        ('path = "file:///etc/passwd"', "url_in_string"),
        ('x = "javascript:alert(1)"', "url_in_string"),
        ('self.post_message("navigate", "x")', "invalid_event"),
        ("self.post_message(some_name, True)", "invalid_event"),
        ("self.post_message()", "invalid_event"),
        ('self.adle_controls = {"bad name!": Slider()}', "invalid_controls"),
        ("self.adle_controls = [Slider()]", "invalid_controls"),
        ("while True:\n    pass", "unbounded_loop"),
        ("while 1:\n    x = 1", "unbounded_loop"),
        # In the pinned runtime a dot given its position as an argument is drawn white.
        ('self.add(Dot([1, 2, 0], color="#269B62"))', "unreliable_call"),
        ('self.add(Dot(point=[1, 2, 0], color="#269B62"))', "unreliable_call"),
        ("self.add(always_redraw(lambda: Dot(ORIGIN, radius=0.1)))", "unreliable_call"),
        # In the pinned runtime set_fill and set_color go wrong with any named argument.
        ("box = Rectangle()\nbox.set_fill(opacity=0.5)", "unreliable_call"),
        ('box = Rectangle()\nbox.set_fill(color="#269B62", opacity=0.5)', "unreliable_call"),
        ('box = Rectangle()\nbox.set_fill("#269B62", opacity=0.5)', "unreliable_call"),
        ("box = Rectangle()\nbox.set_fill(None, opacity=0.5)", "unreliable_call"),
        ('box = Rectangle()\nbox.set_color(color="#269B62")', "unreliable_call"),
        ("box = Rectangle()\nbox.set_fill()", "unreliable_call"),
        # Wherever it is written: in a reaction, and on the way to an animation.
        (
            "box = Rectangle()\nbox.add_reaction(lambda m: m.set_fill(opacity=0.2))",
            "unreliable_call",
        ),
        ("box = Rectangle()\nself.play(box.animate.set_fill(opacity=0.6))", "unreliable_call"),
    ],
)
def test_convention_violations(body: str, code: str) -> None:
    assert code in codes(check_scene_source(scene(body)))


@pytest.mark.parametrize(
    "call",
    [
        'box.set_fill("#269B62", 0.5)',
        "box.set_fill(None, 0.5)",
        'box.set_fill("#269B62")',
        'box.set_color("#269B62")',
        # These take names without trouble, and the guide recommends the first.
        "box.set_stroke(opacity=0.5)",
        'box.set_stroke(color="#269B62", width=6)',
        "box.set_opacity(0.5)",
    ],
)
def test_fill_and_colour_given_in_order_are_accepted(call: str) -> None:
    report = check_scene_source(scene(f"box = Rectangle()\n{call}\nself.add(box)"))
    assert report.violations == ()


def test_the_reason_given_for_a_named_fill_says_how_to_write_it() -> None:
    """It goes into the request for a second try, so it has to be an instruction."""
    report = check_scene_source(scene("box = Rectangle()\nbox.set_fill(opacity=0.5)"))
    [violation] = report.violations
    assert violation.code == "unreliable_call"
    assert "in order, without names" in violation.message
    assert "set_fill(self.blue, 0.3)" in violation.message
    assert "set_fill(None, 0.3)" in violation.message
    assert violation.line is not None


def test_the_fill_fixture_that_is_written_properly_passes() -> None:
    report = check_scene_source((HOSTILE / "fill_in_order.py").read_text(encoding="utf-8"))
    assert report.violations == ()


def test_a_dot_made_with_keywords_and_then_placed_is_accepted() -> None:
    report = check_scene_source(
        scene('self.add(Dot(color="#269B62", radius=0.12).move_to([1, 2, 0]))')
    )
    assert report.violations == ()


@pytest.mark.parametrize(
    "path",
    sorted((REPO_ROOT / "services/core/adle_core/sample_course/scenes").glob("*.py")),
    ids=lambda p: p.name,
)
def test_every_scene_of_the_sample_course_passes(path: Path) -> None:
    report = check_scene_source(path.read_text(encoding="utf-8"))
    assert report.violations == ()
    assert report.ok


def test_init_override_and_special_methods_are_rejected() -> None:
    source = (
        "from manim import *\n\n\nclass Demo(Scene):\n"
        "    def __init__(self):\n        super().__init__()\n"
        "    def __getattr__(self, name):\n        return None\n"
        "    def construct(self):\n        self.wait(0.1)\n"
    )
    assert {"init_override", "unsupported_syntax", "forbidden_attribute"} <= codes(
        check_scene_source(source)
    )


@pytest.mark.parametrize(
    "source",
    [
        "from manim import *\n\n\nclass Demo(ThreeDScene):\n    def construct(self):\n        self.wait(0.1)\n",
        "from manim import *\n\n\n@staticmethod\nclass Demo(Scene):\n    def construct(self):\n        self.wait(0.1)\n",
        "from manim import *\n\n\nclass Demo(Scene):\n    async def construct(self):\n        await self.wait(0.1)\n",
        "from manim import *\n\n\nclass Demo(Scene):\n    pass\n",
        "from manim import *\n\n\nclass Helper:\n    def construct(self):\n        pass\n",
    ],
)
def test_unsupported_scene_shapes(source: str) -> None:
    report = check_scene_source(source)
    assert not report.ok
    assert codes(report) & {"unsupported_scene_base", "unsupported_syntax", "no_scene"}


@pytest.mark.parametrize(
    "source", ["", "   \n", None, 42, b"bytes", "x" * (MAX_SOURCE_CHARS + 1), "a\x00b"]
)
def test_degenerate_inputs_never_raise(source: object) -> None:
    report = check_scene_source(source)
    assert not report.ok
    assert codes(report) <= {"empty", "too_large", "syntax_error"}


def test_deeply_nested_input_is_rejected_not_crashed() -> None:
    report = check_scene_source("x = " + "(" * 5000 + "1" + ")" * 5000)
    assert not report.ok


def test_violations_carry_a_line_number_for_repair() -> None:
    report = check_scene_source(scene("self.wait(0.1)\nx = window"))
    violation = next(v for v in report.violations if v.code == "unknown_name")
    assert violation.line == 7


# -- hashing and vocabulary ------------------------------------------------


def test_content_hash_ignores_line_endings_and_trailing_space() -> None:
    unix = "from manim import *\n\nclass A(Scene):\n    def construct(self):\n        self.wait()\n"
    windows = unix.replace("\n", "\r\n")
    padded = unix.replace("self.wait()", "self.wait()   ") + "\n\n"
    assert content_hash(unix) == content_hash(windows) == content_hash(padded)
    assert content_hash(unix) != content_hash(unix.replace("wait()", "wait(1)"))
    assert normalise_source(windows) == unix


def test_event_vocabulary_matches_the_player_protocol() -> None:
    protocol = (REPO_ROOT / "packages" / "event-protocol" / "src" / "index.ts").read_text("utf-8")
    declared = re.search(r"SCENE_EVENT_NAMES = \[([^\]]+)\]", protocol)
    assert declared is not None
    assert tuple(re.findall(r"'([a-z_]+)'", declared.group(1))) == EVENT_NAMES


def test_a_scene_nested_too_deeply_to_examine_is_refused_not_let_through() -> None:
    deep = "x = " + "(" * 5000 + "1" + ")" * 5000 + "\n"
    report = check_scene_source("from manim import *\n" + deep)
    assert report.ok is False
    assert report.violations
