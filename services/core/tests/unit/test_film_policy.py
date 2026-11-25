"""What a chapter of a film may be, before the film engine runs it (ADR-065).

The engine runs a chapter on this computer, not in the player's frame: the policy is the
first thing between a model's file and the computer. Every hostile file here is one a
model could write; each must be refused without anything of it being run.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from adle_core.film import script
from adle_core.film.policy import (
    MAX_LINES,
    check_chapter_source,
    names,
    said,
    spoken_problem,
    text_problem,
    with_engine_names,
    with_spans_fitted,
)

REPO = Path(__file__).resolve().parents[4]
FIXTURE = (REPO / "fixtures" / "model-answers" / "film-chapter.py").read_text(encoding="utf-8")
EXAMPLE = (
    REPO / "services" / "core" / "adle_core" / "film" / "data" / "example_chapter.py"
).read_text(encoding="utf-8")

FAIR = """
import manimgx as m
import numpy as np
import math

ACCENT = m.YELLOW


def curve(x):
    return np.sin(x) + 0.5 * math.cos(2 * x)


class Chapter(m.Scene):
    def construct(self):
        title = m.Text("The area of a rectangle", font_size=44).to_edge(m.UP)
        self.play(m.Write(title))
        rect = m.Rectangle(width=4, height=2, color=m.BLUE, fill_opacity=0.4)
        self.rect = rect
        w = m.MathTex("4").next_to(rect, m.DOWN)
        h = m.MathTex("2").next_to(rect, m.LEFT)
        self.say("Here is a rectangle, [four wide] and [two tall].", m.Write(w), m.Write(h))
        axes = m.Axes(x_range=[-3, 3], y_range=[-2, 2], axis_config={"include_numbers": True})
        graph = axes.plot(lambda x: curve(x), color=ACCENT)
        self.play(m.Create(axes), m.Create(graph), run_time=2)
        dots = m.VGroup(*[m.Dot(axes.c2p(x, curve(x))) for x in np.linspace(-3, 3, 7)])
        self.play(m.LaggedStart(*[m.FadeIn(d) for d in dots], lag_ratio=0.1))
        self.helper(dots)
        code = m.Code(code_string="total = 0", language="python")
        label = m.Text("mono", font="DejaVu Sans Mono")
        f = m.MathTex(r"F:\\ \\text{newtons (N)}")
        self.play(self.rect.animate.shift(m.LEFT), m.FadeOut(*self.mobjects))
        self.wait()

    def helper(self, group):
        for index, dot in enumerate(group):
            dot.set_color(m.RED if index % 2 else m.GREEN)
        return f"{len(group)} dots, {3.14159:.2f}"
"""

SCENE = "class Chapter(m.Scene):\n    def construct(self):\n"


def bad(body: str, head: str = "import manimgx as m\n") -> str:
    return head + textwrap.dedent(body)


HOSTILE = {
    "another import": bad("import os\n" + SCENE + "        os.system('calc')\n"),
    "from import": bad("from os import system\n" + SCENE + "        system('calc')\n"),
    "an import inside": bad(SCENE + "        import os\n"),
    "dunder import": bad(SCENE + "        __import__('os').system('calc')\n"),
    "open": bad(SCENE + "        open('C:/x.txt').read()\n"),
    "open bound elsewhere": bad(
        "def f():\n    open = 3\n    return open\n" + SCENE + "        open('x')\n"
    ),
    "a class's machinery": bad(SCENE + "        x = ().__class__.__bases__[0].__subclasses__()\n"),
    "a function's globals": bad(SCENE + "        g = self.construct.__globals__\n"),
    "getattr": bad(SCENE + "        g = getattr(m, 'np')\n"),
    "vars": bad(SCENE + "        g = vars(self)\n"),
    "type": bad(SCENE + "        g = type(self)\n"),
    "globals": bad(SCENE + "        g = globals()\n"),
    "eval": bad(SCENE + "        eval('1+1')\n"),
    "exec": bad(SCENE + "        exec('x = 1')\n"),
    "compile": bad(SCENE + "        compile('x', 'y', 'exec')\n"),
    "breakpoint": bad(SCENE + "        breakpoint()\n"),
    "the engine's numpy": bad(SCENE + "        m.np.load('x')\n"),
    "numpy reading a file": bad(
        "import numpy as np\n" + SCENE + "        np.load('x.npy', allow_pickle=True)\n"
    ),
    "an array written out": bad(
        "import numpy as np\n" + SCENE + "        np.zeros(3).tofile('x')\n"
    ),
    "a picture from a file": bad(SCENE + "        m.ImageMobject('C:/Users/me/secret.png')\n"),
    "a drawing from a file": bad(SCENE + "        m.SVGMobject('x.svg')\n"),
    "a sound": bad(SCENE + "        self.add_sound('x.wav')\n"),
    "the engine's voices": bad(SCENE + "        v = m.voices.Fal('model')\n"),
    "the engine's audio": bad(SCENE + "        v = m.audio.Fal('model')\n"),
    "speech of its own": bad(SCENE + "        s = m.Speech(b'', text='x')\n"),
    "a voice for a line": bad(SCENE + "        self.say('Hello there.', voice=3)\n"),
    "a voice for the scene": bad(
        "class Chapter(m.Scene):\n    voice = 3\n    def construct(self):\n        pass\n"
    ),
    "a voice set on itself": bad(SCENE + "        self.voice = 3\n"),
    "what the voice said": bad(SCENE + "        s = self.speech('x')\n"),
    "the engine's settings": bad(SCENE + "        m.config.media_dir = 'C:/'\n"),
    "the typesetter's preamble": bad(
        SCENE + "        m.Text('x', typst_preamble='#read(\"a\")')\n"
    ),
    "a preamble in a mapping": bad(SCENE + "        m.Axes(axis_config={'typst_preamble': 'x'})\n"),
    "the typesetter's code": bad(
        SCENE + "        t = m.MathTex('x')\n        t.typst_code = 'y'\n"
    ),
    "raw Typst": bad(SCENE + "        t = m.Typst('#read(\"x\")')\n"),
    "keywords spread": bad(SCENE + "        o = {}\n        m.Text('x', **o)\n"),
    "a font file": bad(SCENE + "        m.Text('x', font='C:/Windows/Fonts/arial.ttf')\n"),
    "a folder of fonts": bad(SCENE + "        m.Text('x', font_paths=['C:/'])\n"),
    "code from a file": bad(SCENE + "        m.Code('secret.py')\n"),
    "code_file": bad(SCENE + "        m.Code(code_file='secret.py')\n"),
    "a format string": bad(SCENE + "        t = '{0.__class__}'.format(self)\n"),
    "a path": bad(SCENE + "        t = m.Text('C:\\\\Users\\\\me\\\\secret.txt')\n"),
    "a unix path": bad(SCENE + "        t = m.Text('see /etc/passwd/x')\n"),
    "an address": bad(SCENE + "        t = m.Text('see https://example.com/x')\n"),
    "TeX reading a file": bad(SCENE + "        t = m.Tex(r'\\input{secret}')\n"),
    "Typst reading a file": bad(SCENE + "        t = m.Text('#read(\"x\")')\n"),
    "the film being made": bad(SCENE + "        x = self.film\n"),
    "the film's clock": bad(SCENE + "        x = self.clock\n"),
    "the window": bad(SCENE + "        w = m.Window()\n"),
    "a camera of its own": bad(SCENE + "        c = m.Camera()\n"),
    "a three-dimensional scene": bad(
        "class Chapter(m.ThreeDScene):\n    def construct(self):\n        pass\n"
    ),
    "while": bad(SCENE + "        while True:\n            pass\n"),
    "with": bad(SCENE + "        with self as x:\n            pass\n"),
    "try": bad(
        SCENE + "        try:\n            pass\n        except Exception:\n            pass\n"
    ),
    "raise": bad(SCENE + "        raise ValueError('x')\n"),
    "global": bad("x = 1\n" + SCENE + "        global x\n"),
    "print": bad(SCENE + "        print('layout: no problems')\n"),
    "two scenes": bad(
        "class A(m.Scene):\n    def construct(self):\n        pass\n\nclass B(m.Scene):\n    def construct(self):\n        pass\n"
    ),
    "the scene's own render": bad(
        "class A(m.Scene):\n    def construct(self):\n        pass\n    def render(self):\n        pass\n"
    ),
    "the scene's own setup": bad(
        "class A(m.Scene):\n    def construct(self):\n        pass\n    def setup(self):\n        pass\n"
    ),
    "a renderer of its own": bad(SCENE + "        self.renderer = 1\n        x = self.renderer\n"),
    "a decorator": bad(
        "def d(f):\n    return f\n\n@d\ndef g():\n    pass\n" + SCENE + "        pass\n"
    ),
    "a line held in a name": bad(SCENE + "        t = 'Hello'\n        self.say(t)\n"),
    "a line in notation": bad(SCENE + "        self.say('The value of $x^2$ is four.')\n"),
    "a bracket in a bracket": bad(SCENE + "        self.say('The value [of [x] here] is four.')\n"),
    "the engine renamed": bad(SCENE + "        m = 3\n"),
    "an underscore name": bad(SCENE + "        f = lambda __x: __x\n"),
    "a call at the top": bad("m.Text('x')\n" + SCENE + "        pass\n"),
    "no engine": "class Chapter(m.Scene):\n    def construct(self):\n        pass\n",
    "not Python": "import manimgx as m\nclass (:\n",
    "bytes": bad(SCENE + "        b = b'abc'\n"),
    "a default for every text": bad(SCENE + "        m.Text.set_default(color=m.RED)\n"),
    "no construct": bad("class Chapter(m.Scene):\n    def helper(self):\n        pass\n"),
}


def test_a_fair_chapter_passes_and_its_lines_are_read() -> None:
    for source in (FAIR, FIXTURE, EXAMPLE):
        report = check_chapter_source(source)
        assert report.ok, report.violations
        assert report.scene_class is not None
    fixture = check_chapter_source(FIXTURE)
    assert len(fixture.lines) == 14
    assert fixture.lines[0] == "How much floor does a rug cover? [Let us count it.]"


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_a_hostile_chapter_is_refused(name: str) -> None:
    report = check_chapter_source(HOSTILE[name])
    assert not report.ok, name
    assert report.violations


def test_what_is_refused_names_the_line_and_never_runs_anything(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    source = bad(SCENE + f"        open({str(marker)!r}, 'w')\n")
    report = check_chapter_source(source)
    assert not report.ok
    assert any(violation.line == 4 for violation in report.violations)
    assert not marker.exists()


def test_the_names_are_the_pinned_engines() -> None:
    known = names()
    assert known.version == "0.1.1"
    for refused in ("ImageMobject", "SVGMobject", "Sound", "Speech", "Typst", "config", "Camera"):
        assert refused not in known.api
    for allowed in ("Text", "MathTex", "Axes", "Write", "FadeOut", "VGroup", "Table"):
        assert allowed in known.api
    assert "say" in known.members
    for refused in ("film", "clock", "typst_code", "add_sound", "voice", "render"):
        assert refused not in known.members


def test_a_line_said_aloud_is_plain_words_in_whole_brackets() -> None:
    assert spoken_problem("Here is [a circle].") is None
    assert spoken_problem("") == "is empty"
    assert spoken_problem("[]") == "is empty"
    assert "notation" in str(spoken_problem("The value of $x$."))
    assert "notation" in str(spoken_problem(r"The value of \frac{1}{2}."))
    assert "close" in str(spoken_problem("Here [is a circle."))
    assert "inside" in str(spoken_problem("[Here [is] a] circle."))
    assert "longer" in str(spoken_problem("word " * 200))
    assert said("Here is [a circle]  now. ") == "Here is a circle now."


def test_a_line_has_one_animation_for_each_bracketed_span_every_one_said_at_once() -> None:
    lines = (
        "        self.say('Here is [a circle].', m.Write(c))\n"
        "        self.say('Here is [a circle] and [a square].', m.Write(c))\n"
        "        self.say('No brackets at all.', m.Write(c), m.Write(s))\n"
        "        self.say('One [span], two animations.', m.Write(c), m.Write(s))\n"
        "        self.say('Some [spans] [given] as a list.', *[m.Write(c)])\n"
    )
    report = check_chapter_source(
        bad(SCENE + "        c = m.Circle()\n        s = m.Square()\n" + lines)
    )
    assert not report.ok
    told = [(violation.line, violation.message) for violation in report.violations]
    assert told == [
        (
            7,
            "This line has 2 bracketed spans and 1 animation: give one animation for each "
            "span, in the same order.",
        ),
        (
            9,
            "This line has 1 bracketed span and 2 animations: give one animation for each "
            "span, in the same order.",
        ),
    ]


def test_a_chapter_says_a_bounded_number_of_lines() -> None:
    lines = "".join(f"        self.say('Line {index}.')\n" for index in range(MAX_LINES + 1))
    report = check_chapter_source(bad(SCENE + lines))
    assert not report.ok
    assert any("at most" in violation.message for violation in report.violations)


def test_text_a_chapter_may_hold() -> None:
    assert text_problem("Newton's second law: F = ma") is None
    assert text_problem(r"F:\ \text{newtons}") is None
    assert text_problem("see https://example.com") is not None
    assert text_problem(r"C:\Users\me\x.txt") is not None
    assert text_problem('#include "x"') is not None
    assert text_problem("font_path") is not None


@pytest.mark.parametrize(
    ("title", "points"),
    [
        ("The area of a rectangle", ["Count the squares.", "Multiply the sides."]),
        ("See https://example.com/x", ["Read C:\\Users\\me\\secret.txt", '#import "x"']),
        ("/etc/passwd/ and \\input{x}", ["$x^2$ [and] {y}", "", "font_path"]),
        ("", []),
        ("A" * 500, ["B" * 2000] * 9),
    ],
)
def test_a_chapter_in_words_always_passes_whatever_the_course_says(
    title: str, points: list[str]
) -> None:
    chapter = script.plain_chapter(title, points)
    report = check_chapter_source(chapter.source)
    assert report.ok, report.violations
    assert len(report.lines) == len(chapter.lines)
    assert [said(line) for line in report.lines] == [said(line) for line in chapter.lines]


def test_an_engine_name_used_bare_is_written_as_the_engines() -> None:
    slip = bad(
        "RED = 3\n\n\ndef shade(x):\n    return x\n\n\n"
        + SCENE
        + "        dot = Dot(color=WHITE).shift(UP * 2)\n"
        + "        label = m.Text('é: a', color=RED).next_to(dot, DOWN)\n"
        + "        self.play(Create(dot), m.Write(label), shade(1))\n"
    )
    assert not check_chapter_source(slip).ok
    mended = with_engine_names(slip)
    report = check_chapter_source(mended)
    assert report.ok, report.violations
    assert "dot = m.Dot(color=m.WHITE).shift(m.UP * 2)" in mended
    # A name the file defines is its own, and Python's are Python's.
    assert "color=RED" in mended
    assert "self.play(m.Create(dot), m.Write(label), shade(1))" in mended
    assert "next_to(dot, m.DOWN)" in mended


def test_only_a_file_that_imports_the_engine_as_m_is_mended() -> None:
    without = "class Chapter(m.Scene):\n    def construct(self):\n        x = WHITE\n"
    assert with_engine_names(without) == without
    hostile = bad(SCENE + "        open('x')\n        y = WHITE\n")
    mended = with_engine_names(hostile)
    assert "m.WHITE" in mended
    # What the policy refuses is still refused: nothing but a bare name is touched.
    assert not check_chapter_source(mended).ok
    broken = "import manimgx as m\nclass (:\n"
    assert with_engine_names(broken) == broken


def test_a_line_with_more_spans_than_animations_is_mended_and_said_the_same() -> None:
    lines = (
        "        self.say('A [b] and [c] and [d].', m.Write(c))\n"
        "        self.say('Just [words].')\n"
        "        self.say(\n            'Over [two]'\n            ' [lines] here.',\n            m.Write(c),\n        )\n"
        "        self.say('Fine [as] [it is].', m.Write(c), m.Write(s))\n"
    )
    slip = bad(SCENE + "        c = m.Circle()\n        s = m.Square()\n" + lines)
    assert not check_chapter_source(slip).ok
    mended = with_spans_fitted(slip)
    report = check_chapter_source(mended)
    assert report.ok, report.violations
    assert "self.say('A [b] and c and d.', m.Write(c))" in mended
    assert "self.say('Just words.')" in mended
    assert "self.say(\n            'Over [two] lines here.',\n            m.Write(c)," in mended
    assert "self.say('Fine [as] [it is].', m.Write(c), m.Write(s))" in mended
    # What is said does not change: only which words an animation plays in.
    assert [said(line) for line in report.lines] == [
        "A b and c and d.",
        "Just words.",
        "Over two lines here.",
        "Fine as it is.",
    ]


def test_a_line_with_fewer_spans_than_animations_is_not_mended() -> None:
    fewer = bad(
        SCENE + "        c = m.Circle()\n        self.say('A [b].', m.Write(c), m.Write(c))\n"
    )
    assert with_spans_fitted(fewer) == fewer
    assert not check_chapter_source(fewer).ok


def test_numpy_or_math_used_and_not_imported_is_imported() -> None:
    slip = bad(SCENE + "        xs = np.linspace(0, 1, 5)\n        y = math.sqrt(2)\n")
    mended = with_engine_names(slip)
    assert mended.startswith("import manimgx as m\nimport numpy as np\nimport math\n")
    assert check_chapter_source(mended).ok
    # Already imported, or a name of the file's own: left as it is.
    fine = bad("import numpy as np\n" + SCENE + "        xs = np.linspace(0, 1, 5)\n")
    assert with_engine_names(fine) == fine
