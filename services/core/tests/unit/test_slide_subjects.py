"""The pictures subjects other than mathematics need (ADR-061): a timeline, a vessel for an
experiment, a molecule, and lines of code. Each is read as a model may write it, checked,
and drawn by the core; what cannot be drawn is left out and said."""

from __future__ import annotations

import ast
import itertools
import math
from typing import Any

import pytest

from adle_core.generation.layout import LAYOUT_METHODS
from adle_core.generation.scene_policy import check_scene_source
from adle_core.generation.slides import (
    _atom,
    _atom_hue,
    _bonds,
    _code_lines,
    _events,
    _molecule_places,
    _node_places,
    _vessel_changes,
    _vessel_liquid,
    _vessel_outline,
    _vessel_surface,
    compile_slide,
)


def slide(elements: list[dict[str, Any]], steps: list[Any] | None = None) -> Any:
    made = compile_slide({"elements": elements, "steps": steps or []})
    report = check_scene_source(made.source)
    assert report.ok, [violation.message for violation in report.violations]
    return made


def literals(source: str) -> list[str]:
    """Every string in a scene, as Python reads the file."""
    return [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


# -- a timeline -----------------------------------------------------------------------------------


def test_a_timelines_events_are_read_however_they_are_written() -> None:
    events = [{"at": "1957", "text": "Sputnik"}, {"at": "1969", "text": "Apollo 11"}]
    assert _events(events) == events
    assert _events([["1957", "Sputnik"], [1969, "Apollo 11"]]) == events
    assert _events({"1957": "Sputnik", "1969": "Apollo 11"}) == events
    assert (
        _events([{"year": 1957, "event": "Sputnik"}, {"date": "1969", "label": "Apollo 11"}])
        == events
    )


def test_a_timeline_is_drawn_event_by_event_and_said_in_words() -> None:
    made = slide(
        [
            {
                "id": "years",
                "kind": "timeline",
                "label": "The race",
                "events": [["1957", "Sputnik"], ["1961", "The goal"], ["July 1969", "Apollo 11"]],
            }
        ],
        [[{"show": "years.1"}], [{"show": "years.1961"}], [{"highlight": "years.Apollo 11"}]],
    )
    assert made.left_out == []
    assert made.steps == 3
    assert "make_timeline" in made.source
    assert made.described == (
        "Shows a timeline (1957, Sputnik; 1961, The goal; July 1969, Apollo 11)."
    )
    # A date is set as words, never as a formula: "July 1969" is not July times 1969.
    assert "[False, 'July 1969']" in made.source


def test_a_timeline_of_one_event_or_of_too_many_is_left_out() -> None:
    made = compile_slide(
        {
            "elements": [
                {"id": "note", "kind": "text", "text": "One date is not a line."},
                {"id": "one", "kind": "timeline", "events": [["1957", "Sputnik"]]},
                {"id": "many", "kind": "timeline", "events": [[str(y), "x"] for y in range(9)]},
            ]
        }
    )
    assert len(made.left_out) == 2
    assert "make_timeline" not in made.source


# -- a vessel -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("said", "meant"),
    [
        ("bubbles", {"bubbles": True}),
        ("Fizzing", {"bubbles": True}),
        ("still", {"bubbles": False}),
        ("precipitate", {"solid": True}),
        ("dissolved", {"solid": False}),
        ("heat", {"heat": True}),
        ("cool", {"heat": False}),
        ("green", {"liquid": "green"}),
        ("half full", {"level": 0.5}),
        (0.25, {"level": 0.25}),
        (
            {"liquid": "Grey", "level": 2, "bubbles": "yes"},
            {"liquid": "muted", "level": 1.0, "bubbles": True},
        ),
        ({"solid": "white", "heat": False}, {"solid": True, "solid_hue": "ink", "heat": False}),
        ({"precipitate": "no"}, {"solid": False}),
    ],
)
def test_what_is_seen_in_a_vessel_is_read_from_a_word_or_an_object(said: Any, meant: Any) -> None:
    assert _vessel_changes(said) == meant


@pytest.mark.parametrize("nothing", ["shaken", {}, {"smell": "sharp"}, None, True, ["bubbles"]])
def test_a_vessel_set_to_nothing_it_can_show_is_refused(nothing: Any) -> None:
    with pytest.raises(ValueError, match="a vessel is set to"):
        _vessel_changes(nothing)


@pytest.mark.parametrize("shape", ["beaker", "tube", "flask"])
def test_what_is_in_a_vessel_stays_inside_its_glass(shape: str) -> None:
    glass = _vessel_outline(shape)
    left = min(x for x, _ in glass)
    right = max(x for x, _ in glass)
    foot = min(y for _, y in glass)
    brim = max(y for _, y in glass)
    # One line down one side and up the other, with no piece of no length.
    assert all(a != b for a, b in itertools.pairwise(glass))
    assert glass[0][1] == glass[-1][1] == brim
    for level in (0.0, 0.3, 0.6, 1.0):
        liquid = _vessel_liquid(shape, level)
        assert all(left < x < right and foot < y < brim for x, y in liquid)
        assert max(y for _, y in liquid) == pytest.approx(
            max(_vessel_surface(shape, level), foot + 0.07), abs=1e-6
        )
    assert _vessel_surface(shape, 1.0) < brim
    assert _vessel_surface(shape, 0.2) < _vessel_surface(shape, 0.8)


def test_a_vessel_is_named_by_its_shape_and_shows_only_what_has_happened() -> None:
    made = slide(
        [
            {"id": "tube", "kind": "test tube", "liquid": "blue", "label": "copper sulfate"},
            {"id": "jar", "kind": "glass", "level": 80, "solid": "white"},
        ],
        [
            [{"show": ["tube", "jar"]}],
            [
                {"set": "tube", "to": "heat"},
                {"set": "jar", "to": {"solid": False, "bubbles": True}},
            ],
            [{"color": "tube", "to": "green"}, {"hide": "jar"}],
        ],
    )
    assert made.left_out == []
    first, second, third = (
        made.source.split(f"def step_{number}(self):")[1].split("def ")[0] for number in range(3)
    )
    # Drawn where it will be, and not shown before a step says so.
    assert "'tube/flame'" not in first
    assert "'jar/bubbles'" not in first
    assert "'jar/solid'" in first
    assert "GrowFromCenter(self.e['tube/flame'])" in second
    assert "FadeOut(self.e['jar/solid'])" in second
    assert "FadeIn(self.e['jar/bubbles']" in second
    # Colored, it is what is in it that changes: the glass stays as it is.
    assert "self.tint(self.e['tube/liquid'], self.green, 0.5)" in third
    assert "tube/body" not in third
    # Gone, the bubbles go with it, and the solid that had gone already is not faded twice.
    assert "FadeOut(self.e['jar/bubbles'])" in third
    assert "jar/solid" not in third
    assert made.described == (
        "Shows a test tube of copper sulfate and a beaker, with a solid at the bottom."
    )


def test_a_vessel_that_never_bubbles_draws_no_bubbles() -> None:
    made = slide([{"id": "jar", "kind": "vessel", "shape": "flask"}], [[{"show": "jar"}]])
    call = next(line for line in made.source.split("\n") if "self.make_vessel('jar'" in line)
    # No grains, no bubbles, no flame, no name: four empty lists after the liquid's color
    # and how solid it is drawn.
    assert call.rstrip().endswith("self.blue, 0.5, [], self.ink, [], [], [])")


def test_a_vessel_set_to_something_else_keeps_its_other_steps() -> None:
    made = compile_slide(
        {
            "elements": [{"id": "jar", "kind": "beaker"}],
            "steps": [
                [{"show": "jar"}],
                [{"set": "jar", "to": "shaken"}, {"set": "jar", "to": "fizz"}],
            ],
        }
    )
    assert len(made.left_out) == 1
    assert "a vessel is set to" in made.left_out[0]
    assert "FadeIn(self.e['jar/bubbles']" in made.source


# -- a molecule -----------------------------------------------------------------------------------


def test_bonds_are_read_however_they_are_written_and_join_only_atoms_there_are() -> None:
    atoms = ["H", "O", "H", "C"]
    assert _bonds([[1, 2], [2, 3, 2]], atoms) == [[1, 2, 1], [2, 3, 2]]
    assert _bonds(["1-2", "2=3", "3#4"], atoms) == [[1, 2, 1], [2, 3, 2], [3, 4, 3]]
    assert _bonds([{"from": 2, "to": 1, "order": "double"}], atoms) == [[1, 2, 2]]
    # By its symbol, when only one atom has it.
    assert _bonds(["O-C", ["C", "O", 2]], atoms) == [[2, 4, 1]]
    assert _bonds(["H-O"], atoms) == []
    # Nothing joined to itself, to an atom there is not, or twice.
    assert _bonds([[1, 1], [1, 9], [0, 2], [True, 2], "1~2", [1, 2], [2, 1, 3]], atoms) == [
        [1, 2, 1]
    ]
    assert _bonds([[1, 2, 7], [3, 4, 0]], atoms) == [[1, 2, 3], [3, 4, 1]]
    assert _bonds(None, atoms) == []


@pytest.mark.parametrize(
    ("symbol", "drawn"),
    [
        ("H", "\\mathrm{H}"),
        ("Na+", "\\mathrm{Na}^{+}"),
        ("Cl-", "\\mathrm{Cl}^{-}"),
        ("Fe2+", "\\mathrm{Fe}^{2+}"),
        ("O2-", "\\mathrm{O}^{2-}"),
        ("NH4+", "\\mathrm{NH_{4}}^{+}"),
        ("CH3", "\\mathrm{CH_{3}}"),
        ("OH\N{MINUS SIGN}", "\\mathrm{OH}^{-}"),
    ],
)
def test_an_atom_is_drawn_upright_with_its_count_below_and_its_charge_above(
    symbol: str, drawn: str
) -> None:
    assert _atom(symbol) == [True, drawn]


def test_atoms_take_the_colors_chemists_give_them() -> None:
    assert [_atom_hue(symbol) for symbol in ("H", "C", "O", "N", "Cl", "Na+", "OH-")] == [
        "ink", "muted", "coral", "blue", "green", "violet", "coral",
    ]  # fmt: skip
    assert _atom_hue("Xx") == "teal"


def _closest(places: list[list[float]]) -> float:
    return min(
        math.dist(first, second)
        for index, first in enumerate(places)
        for second in places[index + 1 :]
    )


@pytest.mark.parametrize(
    ("count", "bonds"),
    [
        (3, [[1, 2, 1], [2, 3, 1]]),
        (5, [[1, 2, 1], [1, 3, 1], [1, 4, 1], [1, 5, 1]]),
        (
            9,
            [
                [1, 2, 1],
                [2, 3, 1],
                [1, 4, 1],
                [1, 5, 1],
                [1, 6, 1],
                [2, 7, 1],
                [2, 8, 1],
                [3, 9, 1],
            ],
        ),
        (6, [[1, 2, 2], [2, 3, 1], [3, 4, 2], [4, 5, 1], [5, 6, 2], [6, 1, 1]]),
        (2, []),
        (12, [[index, index + 1, 1] for index in range(1, 12)]),
    ],
)
def test_the_atoms_of_a_molecule_stand_apart_and_each_bond_is_one_length(
    count: int, bonds: list[list[int]]
) -> None:
    places = _molecule_places(count, bonds)
    assert len(places) == count
    assert _closest(places) > 0.9
    for first, second, _ in bonds:
        assert math.dist(places[first - 1], places[second - 1]) == pytest.approx(1.15, abs=0.01)
    # Around the middle of its own picture.
    assert abs(max(x for x, _ in places) + min(x for x, _ in places)) < 0.01
    assert abs(max(y for _, y in places) + min(y for _, y in places)) < 0.01


def test_a_ring_is_drawn_as_a_ring() -> None:
    ring = _molecule_places(6, [[1, 2, 1], [2, 3, 1], [3, 4, 1], [4, 5, 1], [5, 6, 1], [6, 1, 1]])
    assert {round(math.hypot(x, y), 2) for x, y in ring} == {1.15}


def test_a_molecule_is_drawn_atom_by_atom_and_a_bond_to_nothing_leaves_the_rest() -> None:
    made = slide(
        [
            {
                "id": "gas",
                "kind": "molecule",
                "atoms": ["O", "C", "O"],
                "bonds": ["O=C", [1, 2, 2], "2=3", [2, 7]],
                "label": "carbon dioxide",
            }
        ],
        [
            [{"show": "gas.2"}],
            [{"show": "gas"}],
            [{"highlight": "gas.2=3"}, {"color": "gas.1", "to": "yellow"}],
        ],
    )
    assert made.left_out == []
    assert "[['gas.b1', 0, 1, [-0.075, 0.075]], ['gas.b2', 1, 2, [-0.075, 0.075]]]" in made.source
    assert "[self.coral, self.muted, self.coral]" in made.source
    assert made.described == "Shows a molecule of carbon dioxide (O, C, O)."
    # An atom is colored by its ball, as a member of a set is by its chip.
    assert "self.tint(self.e['gas.1'][0], self.sun, 0.45)" in made.source


def test_a_molecule_with_no_atoms_or_too_many_is_left_out() -> None:
    made = compile_slide(
        {
            "elements": [
                {"id": "note", "kind": "text", "text": "Nothing to join."},
                {"id": "none", "kind": "molecule", "atoms": []},
                {"id": "many", "kind": "molecule", "atoms": ["C"] * 13},
            ]
        }
    )
    assert len(made.left_out) == 2


# -- code ------------------------------------------------------------------------------------------


def test_code_keeps_its_lines_and_the_spaces_they_begin_with() -> None:
    assert _code_lines("for n in nums:\n\tif n > best:\n\t\tbest = n\n") == [
        "for n in nums:",
        "    if n > best:",
        "        best = n",
    ]
    # What every line begins with is no indentation; an empty line is no line.
    assert _code_lines(["    a = 1", "", "      b = 2   ", "   ", "    return a"]) == [
        "a = 1",
        "  b = 2",
        "return a",
    ]
    assert _code_lines("x = 1\\ny = 2") == ["x = 1", "y = 2"]
    assert len(_code_lines([f"line {number}" for number in range(30)])) == 10  # type: ignore[arg-type]
    assert _code_lines(["x" * 200]) == ["x" * 64]


def test_code_is_drawn_line_by_line_and_its_lines_can_be_pointed_at() -> None:
    made = slide(
        [
            {
                "id": "loop",
                "kind": "code",
                "label": "Python",
                "code": "total = 0\nfor x in [3, 1, 2]:\n    total += x",
            }
        ],
        [[{"show": "loop.1"}], [{"show": "loop"}, {"highlight": "loop.line 3"}]],
    )
    assert made.left_out == []
    assert "['total = 0', 'for x in [3, 1, 2]:', '    total += x']" in made.source
    assert "['total = 0', 'for x in [3, 1, 2]:', 'total += x']" in made.source
    assert "self.ring(['loop.3']" in made.source
    assert made.described == "Shows 3 lines of code (Python)."


def test_whatever_a_line_of_code_says_it_reaches_the_scene_only_as_words() -> None:
    hostile = [
        "'); import os; os.system('calc')  # ",
        '"""; self.post_message("passed", True); """',
        "\\'); window.fetch('example.com')",
        "x = '\\\\'; __import__('os')",
        "{{ }} $ % # & _ ^ ~ \\ ` < > |",
    ]
    made = slide([{"id": "c", "kind": "code", "lines": hostile}], [[{"show": "c"}]])
    assert made.left_out == []
    strings = literals(made.source)
    for line in hostile:
        assert " ".join(line.split()) in strings
    # Nothing of them is code of the scene: the only calls are the template's own.
    calls = {
        node.func.attr
        for node in ast.walk(ast.parse(made.source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & {"system", "fetch", "__import__"}
    assert "import os" not in [line.strip() for line in made.source.split("\n")]


def test_a_link_costs_a_picture_the_element_that_has_it_and_no_more() -> None:
    made = compile_slide(
        {
            "elements": [
                {"id": "call", "kind": "code", "lines": ['get("https://example.com/api")']},
                {"id": "note", "kind": "text", "text": "See javascript:alert(1) for more."},
                {"id": "kept", "kind": "code", "lines": ["get(address)"]},
            ],
            "steps": [[{"show": ["call", "note", "kept"]}]],
        }
    )
    assert [reason.split(": ", 1)[1] for reason in made.left_out[:2]] == [
        "it has a link in it, and a picture shows none"
    ] * 2
    assert "example.com" not in made.source
    assert "alert" not in made.source
    assert "'get(address)'" in made.source
    assert check_scene_source(made.source).ok


def test_code_with_no_line_is_left_out() -> None:
    made = compile_slide(
        {
            "elements": [
                {"id": "note", "kind": "text", "text": "No code yet."},
                {"id": "none", "kind": "code", "lines": ["", "   "]},
                {"id": "odd", "kind": "code", "lines": 7},
            ]
        }
    )
    assert len(made.left_out) == 2
    assert "make_code" not in made.source


# -- what was found while these were looked at in the player ----------------------------------------


def test_nodes_with_long_names_stand_as_far_apart_as_their_names_are_wide() -> None:
    edges = [[0, 1], [1, 2]]
    short = _node_places(3, edges, "row", 1.0)
    assert [x for x, _ in short] == [-2.6, 0.0, 2.6]
    wide = _node_places(3, edges, "row", 3.4)
    assert wide[1][0] - wide[0][0] == pytest.approx(4.3)
    tree = _node_places(3, [[0, 1], [0, 2]], "tree", 3.4)
    assert tree[2][0] - tree[1][0] == pytest.approx(4.3)
    ring = _node_places(5, [], "circle", 3.4)
    assert math.dist(ring[0], ring[1]) >= 3.4 + 0.59
    # A column is one under another, however wide.
    assert _node_places(3, edges, "column", 3.4) == _node_places(3, edges, "column", 0.0)


def test_the_audit_does_not_count_a_value_as_a_drawing_past_the_edge() -> None:
    audit = LAYOUT_METHODS.split("def audit(self):")[1]
    assert "if isinstance(m, ValueTracker):\n                continue" in audit
