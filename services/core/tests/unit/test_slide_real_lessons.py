"""What six real lessons asked of a slide and did not get (2026-11-24, ADR-061): each was
written by a model through a provider, by hand, in a subject other than mathematics, and
each thing below is something one of them wrote. A slide forgives it now."""

from __future__ import annotations

from typing import Any

import pytest

from adle_core.generation.scene_policy import check_scene_source
from adle_core.generation.slides import (
    CLEAR,
    _offset,
    _outward,
    _relation,
    _token,
    _vessel_changes,
    compile_slide,
)
from adle_core.generation.speech import has_marks, small_as_tex


def slide(elements: list[dict[str, Any]], steps: list[Any] | None = None) -> Any:
    made = compile_slide({"elements": elements, "steps": steps or []})
    report = check_scene_source(made.source)
    assert report.ok, [violation.message for violation in report.violations]
    return made


def step(made: Any, number: int) -> str:
    return str(made.source.split(f"def step_{number}(self):")[1].split("    def ")[0])


# -- characters written small, and a quantity with its unit ------------------------------------------


@pytest.mark.parametrize(
    ("written", "tex"),
    [
        ("H\N{SUBSCRIPT TWO}O", "\\mathrm{H_2O}"),
        ("Na\N{SUPERSCRIPT PLUS SIGN}", "\\mathrm{Na}^+"),
        (
            "SO\N{SUBSCRIPT FOUR}\N{SUPERSCRIPT TWO}\N{SUPERSCRIPT MINUS}",
            "\\mathrm{SO_4}^{2-}",
        ),
        (
            "C\N{SUBSCRIPT ONE}\N{SUBSCRIPT TWO}H\N{SUBSCRIPT TWO}\N{SUBSCRIPT TWO}",
            "\\mathrm{C_{12}H_{22}}",
        ),
        # A square is a square, of a variable or of a unit: nothing of chemistry in it.
        ("x\N{SUPERSCRIPT TWO} + y\N{SUPERSCRIPT TWO}", "x^2 + y^2"),
        ("E = mc\N{SUPERSCRIPT TWO}", "E = mc^2"),
        ("plain words", "plain words"),
    ],
)
def test_characters_written_small_are_written_as_a_formula_writes_them(
    written: str, tex: str
) -> None:
    assert small_as_tex(written) == tex
    assert has_marks(written) is (written != tex)


def test_a_name_with_small_characters_is_set_as_a_formula_which_can_show_them() -> None:
    assert _token("H\N{SUBSCRIPT TWO}O") == [True, "\\mathrm{H_2O}"]
    made = slide(
        [{"id": "jar", "kind": "vessel", "label": "H\N{SUBSCRIPT TWO}O"}], [[{"show": "jar"}]]
    )
    assert "\N{SUBSCRIPT TWO}" not in made.source
    assert "[True, '\\\\mathrm{H_2O}']" in made.source


@pytest.mark.parametrize(
    ("written", "drawn"),
    [
        ("10 N", "10\\,\\mathrm{N}"),
        ("4 kg", "4\\,\\mathrm{kg}"),
        ("-3 V", "-3\\,\\mathrm{V}"),
        ("12 m/s", "12\\,\\mathrm{m}/\\mathrm{s}"),
        ("2.5 m/s\N{SUPERSCRIPT TWO}", "2.5\\,\\mathrm{m}/\\mathrm{s}^2"),
    ],
)
def test_a_quantity_is_a_number_and_its_unit_upright(written: str, drawn: str) -> None:
    assert _token(written) == [True, drawn]


def test_what_is_not_a_quantity_is_read_as_it_was() -> None:
    assert _token("2x") == [True, "2x"]
    assert _token("10") == [True, "10"]
    assert _token("3 apples") == [False, "3 apples"]
    assert _token("fib(3)") == [False, "fib(3)"]


# -- a liquid with no color ------------------------------------------------------------------------------


def test_a_liquid_can_have_no_color_and_is_still_seen_to_be_there() -> None:
    for said in ("colorless", "Clear", "transparent", "no color"):
        assert _vessel_changes(said) == {"liquid": CLEAR}
        assert _vessel_changes({"liquid": said}) == {"liquid": CLEAR}
    made = slide(
        [{"id": "jar", "kind": "vessel", "liquid": "pink"}],
        [
            [{"show": "jar"}],
            [{"set": "jar", "to": {"liquid": "colorless", "bubbles": False}}],
            [{"color": "jar", "to": "blue"}],
            [{"color": "jar", "to": "colorless"}],
        ],
    )
    assert made.left_out == []
    assert "self.tint(self.e['jar/liquid'], self.ink, 0.1)" in step(made, 1)
    assert "self.tint(self.e['jar/liquid'], self.blue, 0.5)" in step(made, 2)
    assert "self.tint(self.e['jar/liquid'], self.ink, 0.1)" in step(made, 3)
    begun = slide([{"id": "jar", "kind": "vessel", "liquid": "colorless"}], [[{"show": "jar"}]])
    call = next(line for line in begun.source.split("\n") if "self.make_vessel('jar'" in line)
    assert ", self.ink, 0.1, [], " in call


# -- an arrow out of a thing ---------------------------------------------------------------------------


def test_an_arrow_points_out_of_a_thing_however_that_is_written() -> None:
    assert _outward({"from": "cart", "to": {"right of": "cart"}})["toward"] == "right"
    assert _outward({"to": {"below": "cart", "x": 3}}) == {
        "from": "cart",
        "to": "cart",
        "toward": "below",
    }
    assert _outward({"from": "cart", "direction": "Up"})["toward"] == "above"
    assert _outward({"from": "cart", "toward": "left"})["toward"] == "left"
    # From one thing to beside another is an arrow between the two.
    between = _outward({"from": "cart", "to": {"right of": "wall"}})
    assert (between["from"], between["to"], between.get("toward")) == ("cart", "wall", None)
    assert "toward" not in _outward({"from": "cart", "to": "wall", "direction": "sideways"})


def test_a_push_is_drawn_out_of_what_it_pushes_and_its_words_can_change() -> None:
    made = slide(
        [
            {"id": "cart", "kind": "shape", "shape": "rectangle", "label": "2 kg"},
            {"id": "push", "kind": "arrow", "from": "cart", "to": {"right of": "cart", "x": 3},
             "label": "5 N"},
            {"id": "weight", "kind": "arrow", "from": "cart", "direction": "down"},
            {"id": "rope", "kind": "line", "from": "cart", "toward": "above"},
        ],
        [
            [{"show": ["cart", "push", "weight", "rope"]}],
            [{"set": "push", "to": {"label": "10 N"}}, {"set": "weight", "to": "20 N"}],
        ],
    )  # fmt: skip
    # Right is 3, below 0, above 1; a line counts on from an arrow's 5 at 9.
    assert "self.link(['cart'], ['cart'], 8, " in made.source
    assert "self.link(['cart'], ['cart'], 5, " in made.source
    assert "self.link(['cart'], ['cart'], 10, " in made.source
    changed = step(made, 1)
    assert "fresh = self.tag(self.e['push'], [True, '10\\\\,\\\\mathrm{N}'])" in changed
    assert "FadeTransform(self.e['push/name'], fresh)" in changed
    # An arrow with no words has none to set: that is said, and the rest is done.
    assert made.left_out == ["an action: set: that arrow has no words to set"]


# -- a list whose cells change -------------------------------------------------------------------------


def test_a_grid_is_set_to_rows_like_its_own_and_only_what_changed_is_drawn_again() -> None:
    made = slide(
        [{"id": "list", "kind": "grid", "rows": [["5", "1", "4", ""]]}],
        [
            [{"show": "list"}],
            [{"set": "list", "to": {"rows": [["1", "5", "4", ""]]}}],
            [{"set": "list", "to": [["1", "4", "5"]]}, {"set": "list.1.4", "to": 12}],
            [{"set": "list.1.1", "to": "1"}],
        ],
    )
    assert made.left_out == []
    first, second, third = step(made, 1), step(made, 2), step(made, 3)
    assert first.count("self.recell(") == 2
    assert "self.recell('list.1.1', [True, '1'], " in first
    assert "self.recell('list.1.2', [True, '5'], " in first
    assert second.count("self.recell(") == 3
    assert "self.recell('list.1.4', [True, '12'], " in second
    # Set to what it holds already, nothing is drawn.
    assert "recell" not in third
    # A cell is made wide enough for the widest thing it will hold.
    narrow = slide([{"id": "list", "kind": "grid", "rows": [["5"]]}], [[{"show": "list"}]])
    wide = slide(
        [{"id": "list", "kind": "grid", "rows": [["5"]]}],
        [[{"show": "list"}], [{"set": "list.1.1", "to": "1234567"}]],
    )

    def side(made: Any) -> float:
        call = next(line for line in made.source.split("\n") if "self.make_grid('list'" in line)
        return float(call.split("]], 1, 1, ")[1].split(",")[0])

    assert side(wide) > side(narrow)


@pytest.mark.parametrize(
    "value",
    [{"rows": [["1"], ["2"]]}, [["1", "2", "3", "4", "5"]], "sorted", {"rows": "1 2 3"}, [1, 2]],
)
def test_a_grid_set_to_something_of_another_shape_is_left_as_it_is(value: Any) -> None:
    made = compile_slide(
        {
            "elements": [{"id": "list", "kind": "grid", "rows": [["5", "1", "4", "2"]]}],
            "steps": [[{"show": "list"}], [{"set": "list", "to": value}]],
        }
    )
    assert made.left_out == ["an action: set: a grid is set to rows like its own"]
    assert "recell" not in made.source.split("def step_0")[1]


def test_an_arrow_moves_to_what_it_joins_next_and_takes_its_words_along() -> None:
    made = slide(
        [
            {"id": "list", "kind": "grid", "rows": [["5", "1", "4"]]},
            {"id": "compare", "kind": "arrow", "from": "list.1.1", "to": "list.1.2",
             "label": "compare"},
        ],
        [
            [{"show": ["list", "compare"]}],
            [{"move": "compare", "to": {"from": "list.1.2", "to": "list.1.3"}}],
            [{"move": "compare", "to": {"to": "list.1.1"}}],
            [{"move": "compare", "to": {"from": "nowhere", "to": "list.1.3"}}],
        ],
    )  # fmt: skip
    # From cell to cell of one grid an arrow arcs over them: cells that touch leave a
    # straight one no length.
    assert "self.link(['list.1.1'], ['list.1.2'], 4, " in made.source
    moved = step(made, 1)
    assert "fresh = self.link(['list.1.2'], ['list.1.3'], 4, " in moved
    assert "Transform(self.e['compare'], fresh)" in moved
    assert "Transform(self.e['compare/name'], self.tag(fresh, [False, 'compare']))" in moved
    # An end left unsaid is the end it was written with.
    assert "fresh = self.link(['list.1.1'], ['list.1.1'], 4, " in step(made, 2)
    assert made.left_out == [
        'a step names "nowhere", which is not on the stage'
    ] or made.left_out == ["an action: move: it joins nothing that is on the stage"]


# -- nodes, and an edge past the ones between its ends -------------------------------------------------


def test_an_edge_goes_round_the_nodes_between_its_ends() -> None:
    made = slide(
        [
            {"id": "why", "kind": "nodes", "layout": "row", "nodes": ["a", "b", "c", "d"],
             "edges": [["a", "d"], ["b", "d"], ["c", "d"]]},
            {"id": "down", "kind": "nodes", "layout": "column", "nodes": ["a", "b", "c"],
             "edges": [[1, 3], [1, 2]], "directed": False},
            {"id": "ring", "kind": "nodes", "layout": "circle", "nodes": ["a", "b", "c", "d"],
             "edges": [[1, 3]]},
        ],
        [[{"show": ["why", "down", "ring"]}]],
    )  # fmt: skip
    assert "[['why.e1', 0, 3, 1], ['why.e2', 1, 3, 1], ['why.e3', 2, 3, 0]]" in made.source
    assert "[['down.e1', 0, 2, 2], ['down.e2', 0, 1, 0]]" in made.source
    # Across a ring an edge is a chord, which meets no node.
    assert "[['ring.e1', 0, 2, 0]]" in made.source
    # An arc is drawn in; a straight arrow grows.
    assert "Create(self.e['why.e1'])" in made.source
    assert "GrowArrow(self.e['why.e3'])" in made.source
    # The arc with no head is given its bend by place: by name the player draws nothing
    # finite (seen in the player, 2026-11-24).
    assert "ArcBetweenPoints(tail, tip, bend)" in made.source
    assert "ArcBetweenPoints(tail, tip, angle" not in made.source
    assert "CurvedArrow(tail, tip, color=self.muted, angle=bend)" in made.source


# -- what is set is never shown -------------------------------------------------------------------------


def test_a_value_a_step_shows_is_passed_over_and_the_scene_still_runs() -> None:
    made = compile_slide(
        {
            "elements": [
                {"id": "cell", "kind": "shape", "shape": "circle", "label": "cell"},
                {"id": "salt", "kind": "param", "value": 0.2, "min": 0, "max": 1, "slider": True},
            ],
            "steps": [[{"show": ["cell", "salt"]}], [{"highlight": "salt"}, {"hide": "salt"}]],
        }
    )
    assert made.left_out.count("a step shows a value, which is set and not drawn") == 3
    assert "self.e['salt']" not in made.source
    assert check_scene_source(made.source).ok


# -- one thing in the places of others -------------------------------------------------------------------


def test_what_is_moved_onto_something_never_shown_stands_for_it_from_then_on() -> None:
    oxygen = {"kind": "molecule", "atoms": ["O", "O"], "bonds": [[1, 2, 2]]}
    made = slide(
        [
            {"id": "wall", "kind": "shape", "shape": "rectangle", "label": "membrane"},
            {"id": "out", "place": "top", **oxygen},
            {"id": "mid", "place": "center", **oxygen},
            {"id": "in", "place": "bottom", **oxygen},
        ],
        [
            [{"show": ["wall", "out"]}],
            [{"move": "out", "to": "mid"}],
            [{"move": "mid", "to": "in"}],
            [{"highlight": "in"}, {"color": "in", "to": "yellow"}, {"hide": "mid"}],
        ],
    )
    assert made.left_out == []
    # "mid" and "in" are never drawn on the stage: it is "out" that moves, and is pointed at.
    for number in (1, 2):
        assert "self.shift_to(['out.b1', 'out.1', 'out.2']" in step(made, number)
    shown = made.source.split("def step_0")[1]
    for ghost in ("'mid.1'", "'in.1'"):
        assert f"GrowFromCenter(self.e[{ghost}])" not in shown
        assert f"self.ring([{ghost}" not in shown
    assert "self.ring(['out.b1', 'out.1', 'out.2']" in step(made, 3)
    assert "FadeOut(self.e['out.1'])" in step(made, 3)


# -- beside something ----------------------------------------------------------------------------------------


def test_beside_another_element_whatever_else_is_said_with_it() -> None:
    assert _relation({"left of": "track", "x": 1}) == (2, "track")
    assert _relation({"y": -2, "Below": "rule"}) == (0, "rule")
    assert _relation({"x": 1, "y": 2}) is None
    assert _offset({"left of": "rule", "x": 9, "y": -9}) == (4.0, -2.4)
    assert _offset({"left of": "rule", "y": True}) == (0.0, 0.0)
    assert _offset("left") == (0.0, 0.0)


def test_two_things_on_one_side_of_the_same_thing_do_not_lie_over_each_other() -> None:
    def beside(steps: list[Any], **more: Any) -> str:
        made = slide(
            [
                {"id": "law", "kind": "math", "tex": "a = F / m"},
                {"id": "one", "kind": "text", "text": "first", "place": {"below": "law", **more}},
                {"id": "two", "kind": "text", "text": "second", "place": {"below": "law"}},
            ],
            steps,
        )
        return str(made.source.split("def build(self):")[1].split("    def ")[0])

    # Seen at once, the second stands beyond the first; where there is no room there, it
    # goes beside it, never back onto what they both stand under.
    together = beside([[{"show": ["law", "one", "two"]}]])
    assert "self.stand_beside('one', 'law', [0, 1])" in together
    assert "self.stand_beside('two', 'one', [0, 3, 2])" in together
    # One that takes the other's place stands where it stood.
    in_turn = beside([[{"show": ["law", "one"]}], [{"hide": "one"}, {"show": "two"}]])
    assert "self.stand_beside('two', 'law', [0, 1])" in in_turn
    # One put a little along from there has a place of its own.
    apart = beside([[{"show": ["law", "one", "two"]}]], x=2)
    assert "self.stand_beside('two', 'law', [0, 1])" in apart
    assert "self.e['one'].shift(RIGHT * 2.0 + UP * 0.0)" in apart


def test_an_offset_is_taken_along_the_side_and_never_toward_the_thing() -> None:
    made = slide(
        [
            {"id": "law", "kind": "math", "tex": "a = F / m"},
            {"id": "up", "kind": "shape", "place": {"left of": "law", "y": 2, "x": 1}},
            {"id": "down", "kind": "shape", "place": {"left of": "law", "y": -2}},
        ],
        [[{"show": ["law", "up", "down"]}]],
    )
    assert "self.e['up'].shift(RIGHT * 0.0 + UP * 2.0)" in made.source
    assert "self.e['down'].shift(RIGHT * 0.0 + UP * -2.0)" in made.source
    # Each has a place of its own: neither stands beyond the other.
    assert "self.stand_beside('down', 'law', [2, 3])" in made.source
