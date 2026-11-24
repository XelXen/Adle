"""Slides (ADR-049): a part's picture as a script the model writes and the core draws,
paced by words of the narration marked in [brackets]."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from adle_core.generation.drafts import (
    LessonContext,
    ObjectiveRef,
    _cued,
    _marked,
    _paced,
    _step_seconds,
    compile_lesson,
    parse_lesson_draft,
)
from adle_core.generation.figures import _cell
from adle_core.generation.layout import LAYOUT_METHODS
from adle_core.generation.prompts import visual_example
from adle_core.generation.scene_policy import check_scene_source
from adle_core.generation.slides import KINDS, VERBS, SlideError, _fitted, compile_slide
from adle_core.lessons.bundle import inspect_scene, parse_bundle
from adle_core.tools.export_slides import EXAMPLES, steps, written
from tests.support.model import LESSON

SLIDES = Path(__file__).resolve().parents[4] / "apps" / "desktop" / "e2e" / "fixtures" / "slides"


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_every_example_is_a_scene_the_policy_accepts_paced_in_its_steps(name: str) -> None:
    slide = compile_slide(EXAMPLES[name])
    assert slide.left_out == []
    report = check_scene_source(slide.source)
    assert report.ok, [violation.message for violation in report.violations]
    artifact = inspect_scene("scn_1", "A slide.", slide.source)
    assert artifact.steps == slide.steps
    assert "step" in artifact.events
    assert artifact.interactive is slide.interactive
    # One step for each step written, and a live page for a slider.
    assert slide.steps == len(EXAMPLES[name]["steps"]) + (1 if slide.interactive else 0)


def test_the_examples_use_every_kind_of_element_and_every_verb() -> None:
    kinds = {element["kind"] for example in EXAMPLES.values() for element in example["elements"]}
    assert kinds == set(KINDS)
    verbs = {
        key
        for example in EXAMPLES.values()
        for step in example["steps"]
        for action in step
        for key in action
        if key in VERBS
    }
    assert verbs == set(VERBS)


def test_the_slides_the_player_runs_are_what_the_module_writes() -> None:
    files = {path.name: path.read_text(encoding="utf-8") for path in SLIDES.glob("*.py")}
    assert files == written(), "Run `npm run slides` and commit what it writes."
    plan = json.loads((SLIDES / "steps.json").read_text(encoding="utf-8"))
    assert plan == steps()


def test_what_cannot_be_drawn_is_left_out_and_said_and_the_rest_is_drawn() -> None:
    slide = compile_slide(
        {
            "elements": [
                {"id": "omega", "kind": "set", "items": ["H", "T"]},
                {"id": "ghost", "kind": "hologram"},
                {"id": "link", "kind": "arrow", "from": "omega.H", "to": "nowhere"},
                {"id": "bad", "kind": "curve", "on": "omega", "f": "x"},
                {"id": "omega", "kind": "text", "text": "a second omega"},
            ],
            "steps": [
                [{"show": "omega"}, {"show": "ghost"}],
                [{"highlight": "omega.Z"}, {"highlight": "omega.T"}],
                [{"color": "omega.H"}],
                [{"spin": "omega"}],
            ],
        }
    )
    said = " | ".join(slide.left_out)
    assert '"hologram" is not a kind of element' in said
    assert '"link": it joins "nowhere"' in said
    assert '"bad": it is drawn on "omega", which is not axes' in said
    assert 'a second element named "omega"' in said
    assert 'a step names "omega.Z"' in said
    assert "color: it names no color there is" in said
    assert "it does none of" in said
    # What is left is drawn, and paced in the steps that did something.
    assert check_scene_source(slide.source).ok
    assert slide.steps >= 2


def test_a_slide_with_nothing_that_can_be_drawn_is_refused() -> None:
    with pytest.raises(SlideError):
        compile_slide({"elements": [{"id": "x", "kind": "arrow", "from": "a", "to": "b"}]})
    with pytest.raises(SlideError):
        compile_slide("a picture of a coin")


def test_a_script_without_steps_shows_everything_at_once() -> None:
    slide = compile_slide({"elements": [{"id": "rule", "kind": "math", "tex": "a^2 + b^2 = c^2"}]})
    assert slide.steps == 1
    assert "Write(self.e['rule'])" in slide.source


def test_text_from_the_script_reaches_the_scene_only_as_quoted_literals() -> None:
    hostile = '"); import os; os.system("x"); ("'
    slide = compile_slide(
        {
            "elements": [
                {"id": "note", "kind": "text", "text": hostile},
                {"id": "s", "kind": "words", "text": hostile},
                {"id": "chips", "kind": "set", "items": [hostile[:40]]},
            ],
            "steps": [[{"show": ["note", "s", "chips"]}]],
        }
    )
    report = check_scene_source(slide.source)
    assert report.ok
    assert "import os" not in slide.source.replace(repr(hostile), "")


def test_a_curve_s_formula_is_arithmetic_and_nothing_else() -> None:
    slide = compile_slide(
        {
            "elements": [
                {"id": "plane", "kind": "axes", "x": [0, 1]},
                {"id": "f", "kind": "curve", "on": "plane", "f": "__import__('os')"},
            ],
        }
    )
    assert any('"f":' in reason for reason in slide.left_out)
    assert "__import__" not in slide.source


def test_colors_in_a_formula_are_the_stage_s_hues() -> None:
    slide = compile_slide(
        {
            "elements": [
                {
                    "id": "rule",
                    "kind": "math",
                    "tex": "\\frac{\\color{yellow}{1}}{\\color{blue}{2}}",
                }
            ]
        }
    )
    assert "\\\\color{#E9BE5A}" in slide.source
    assert "\\\\color{#7BA4EE}" in slide.source
    assert "yellow" not in slide.source


def test_parts_of_a_formula_and_of_a_sentence_can_be_pointed_at() -> None:
    slide = compile_slide(
        {
            "elements": [
                {"id": "rule", "kind": "math", "tex": "{{P(E)}} = {{\\frac{1}{2}}}"},
                {"id": "s", "kind": "words", "text": "The quick brown fox."},
            ],
            "steps": [
                [{"show": ["rule", "s"]}],
                [{"color": "rule.2", "to": "green"}, {"highlight": "s.quick brown"}],
                [{"color": ["s.fox", "s.1"], "to": "blue"}],
            ],
        }
    )
    assert slide.left_out == []
    assert "self.e['rule.2'] = self.e['rule'][2]" in slide.source
    assert "self.ring(['s.2', 's.3'], self.sun)" in slide.source
    assert "self.tint(self.e['s.4'], self.blue, 0)" in slide.source


# -- the narration's cues --------------------------------------------------------------------


def test_bracketed_words_are_cues_and_are_said_without_their_brackets() -> None:
    said, cues = _cued(_marked("Flip a coin: there are [two outcomes], [heads] and tails."))
    assert said == "Flip a coin: there are two outcomes, heads and tails."
    assert [said[cue:].split()[0] for cue in cues] == ["two", "heads"]


def test_brackets_of_mathematics_are_not_cues() -> None:
    for text in ("Pick a number in [0, 1].", "The interval [2.5] alone.", "The mean $E[X]$ here."):
        said, cues = _cued(_marked(text))
        assert said == text
        assert cues == []


def test_a_cue_may_hold_mathematics_said_in_words() -> None:
    lesson = compiled_with_slide(
        beats=[{"say": "So [$x^2$ grows] faster than $x$ does."}],
        steps=[[{"show": "rule"}], [{"highlight": "rule"}]],
    )
    beat = lesson["segments"][0]["narration"][0]
    assert "$" not in beat["text"]
    assert "[" not in beat["text"]
    assert beat["text"][beat["cues"][0] :].startswith("x squared")


def _beats(*lines: tuple[str, list[int]]) -> list[dict[str, Any]]:
    return [{"text": text, **({"cues": cues} if cues else {})} for text, cues in lines]


def test_cues_are_fitted_to_the_steps_of_the_slide() -> None:
    narration = _beats(("First this. Then that. And then more.", [12]), ("Last of all.", []))
    # One cue for each step after the first.
    assert _paced(narration, 2)[0]["cues"] == [12]
    # Too many: the ones past the last step are dropped.
    assert _paced(narration, 1) == _beats(
        ("First this. Then that. And then more.", []), ("Last of all.", [])
    )
    # Too few: the rest where a sentence begins, after the last one there is.
    paced = _paced(narration, 4)
    places = [(line, cue) for line, beat in enumerate(paced) for cue in beat.get("cues", [])]
    assert places == [(0, 12), (0, 23), (1, 0)]


def test_a_cue_on_the_first_words_marks_the_first_step_and_is_dropped() -> None:
    narration = _beats(("Look at this coin. It lands heads.", [0, 19]))
    assert _paced(narration, 2)[0]["cues"] == [19]


# -- a lesson with slides --------------------------------------------------------------------

CONTEXT = LessonContext(
    lesson_id="les_0123456789abcdef0123",
    course_id="crs_0123456789abcdef0123",
    concept_id="con_0123456789abcdef0123",
    objectives=[ObjectiveRef("obj_00000000000000000001", "Compute a weighted sum by hand.")],
)

VISUAL = {
    "elements": [{"id": "rule", "kind": "math", "tex": "x^2", "place": "center"}],
    "steps": [[{"show": "rule"}]],
}


def compiled_with_slide(
    beats: list[dict[str, Any]], steps: list[Any], visual: dict[str, Any] | None = None
) -> dict[str, Any]:
    draft = copy.deepcopy(LESSON)
    segment = {
        "type": "explanation",
        "title": "Squares grow",
        "beats": beats,
        "visual": {**(visual or VISUAL), "steps": steps},
    }
    draft["segments"] = [segment, *draft["segments"][1:]]
    compiled = compile_lesson(parse_lesson_draft(draft), CONTEXT)
    return compiled.lesson


def test_a_part_with_a_visual_gets_a_slide_paced_by_its_words() -> None:
    draft = copy.deepcopy(LESSON)
    draft["segments"][0] = {
        "type": "explanation",
        "title": "One flip",
        "beats": [
            {"say": "Flip a coin. There are [two outcomes]."},
            {"say": "We call the one we care about [an event], here heads."},
        ],
        "visual": copy.deepcopy(EXAMPLES["sample_space"])
        | {"steps": EXAMPLES["sample_space"]["steps"][:3]},
    }
    compiled = compile_lesson(parse_lesson_draft(draft), CONTEXT)
    segment = compiled.lesson["segments"][0]
    assert segment["scene"]["scene_id"] == compiled.figures[0].scene_id
    assert compiled.figures[0].kind == "slide"
    narration = segment["narration"]
    assert narration[0]["text"] == "Flip a coin. There are two outcomes."
    cues = [(line, cue) for line, beat in enumerate(narration) for cue in beat.get("cues", [])]
    assert len(cues) == 2
    # The lesson and its slide are taken as a lesson is stored.
    bundle = parse_bundle(
        {
            "lesson": compiled.lesson,
            "scenes": [
                {"id": figure.scene_id, "purpose": figure.title, "source": figure.source}
                for figure in compiled.figures
            ],
            "pending_scene_ids": [brief.scene_id for brief in compiled.scenes],
        }
    )
    assert bundle.scenes[0].steps == 3


def test_a_part_without_a_slide_keeps_its_words_and_loses_its_cues() -> None:
    draft = copy.deepcopy(LESSON)
    draft["segments"][0]["beats"] = [{"say": "There are [two outcomes] here."}]
    draft["segments"][0].pop("visual", None)
    compiled = compile_lesson(parse_lesson_draft(draft), CONTEXT)
    beat = compiled.lesson["segments"][0]["narration"][0]
    assert beat["text"] == "There are two outcomes here."
    assert "cues" not in beat


def test_a_visual_that_cannot_be_drawn_leaves_its_part_in_words() -> None:
    lesson = compiled_with_slide(
        beats=[{"say": "Look at [this]."}],
        steps=[],
        visual={"elements": [{"id": "x", "kind": "hologram"}]},
    )
    segment = lesson["segments"][0]
    assert "scene" not in segment
    assert segment["narration"][0] == {"text": "Look at this."}


def test_the_same_line_on_the_board_twice_in_a_row_is_shown_once() -> None:
    draft = copy.deepcopy(LESSON)
    draft["segments"][0]["beats"] = [
        {"say": "One.", "show": "$\\Omega = \\{H, T\\}$"},
        {"say": "Two.", "show": "$\\Omega = \\{H, T\\}$"},
        {"say": "Three.", "show": "$\\omega \\in \\Omega$"},
    ]
    compiled = compile_lesson(parse_lesson_draft(draft), CONTEXT)
    shown = [beat.get("show") for beat in compiled.lesson["segments"][0]["narration"]]
    assert shown == ["$\\Omega = \\{H, T\\}$", None, "$\\omega \\in \\Omega$"]


# -- a table's cells -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cell", "drawn"),
    [
        ("\\{H, T\\}", [True, "\\{H, T\\}"]),
        ("\\\\{H, T\\\\}", [True, "\\{H, T\\}"]),
        ("\\emptyset", [True, "\\emptyset"]),
        ("E_1 (whole space)", [True, "E_1 (\\text{whole space})"]),
        ("snake_case", [False, "snake_case"]),
        ("heads", [False, "heads"]),
    ],
)
def test_tex_written_without_dollar_signs_in_a_cell_is_set_as_a_formula(
    cell: str, drawn: list[Any]
) -> None:
    assert _cell(cell) == drawn


def test_the_prompt_s_own_example_is_a_slide_with_a_cue_for_each_later_step() -> None:
    example = visual_example()
    slide = compile_slide(example["visual"])
    assert slide.left_out == []
    said = [_cued(_marked(beat["say"])) for beat in example["beats"]]
    assert sum(len(cues) for _, cues in said) == slide.steps - 1


def test_what_is_drawn_from_a_moving_point_moves_with_it() -> None:
    slide = compile_slide(
        {
            "elements": [
                {"id": "h", "kind": "param", "value": 1, "min": 0.1, "max": 2, "slider": True},
                {"id": "plane", "kind": "axes", "x": [0, 4]},
                {"id": "f", "kind": "curve", "on": "plane", "f": "x^2"},
                {"id": "P", "kind": "point", "on": "f", "x": 1},
                {"id": "Q", "kind": "point", "on": "f", "x": "h"},
                {"id": "secant", "kind": "line", "from": "P", "to": "Q", "label": "secant"},
                {"id": "note", "kind": "label", "on": "Q", "text": "moves"},
            ],
            "steps": [[{"show": ["f", "P", "Q", "secant", "note"]}]],
        }
    )
    assert slide.left_out == []
    assert "self.e['secant'] = always_redraw(lambda: self.link(['P'], ['Q'], 3, self.muted))" in (
        slide.source
    )
    assert "self.followers.append('secant/name')" in slide.source
    assert "self.e['note'] = always_redraw(" in slide.source


def test_what_real_models_wrote_is_taken_as_they_meant_it() -> None:
    """Each of these is a slip a real model made on 2026-11-22, copying the prompt's own
    examples: a part named with the example's prefix, items written as parts, a cell
    counted from 0, a sentence left empty to be filled by a step, and a symbol of sets in
    plain words."""
    slide = compile_slide(
        {
            "elements": [
                {"id": "sentence", "kind": "words", "text": "The cat chased the mouse."},
                {"id": "subject", "kind": "label", "on": "sentence.s.1-2", "text": "subject"},
                {"id": "omega_die", "kind": "set", "items": ["omega.1", "omega.2", "omega.3"]},
                {"id": "array", "kind": "grid", "rows": [["10", "20", "30"]]},
                {"id": "pointer", "kind": "arrow", "from": "omega_die", "to": "array.0.2"},
                {"id": "later", "kind": "words", "text": ""},
                {"id": "note", "kind": "text", "text": "Event E \u2286 \u03a9"},
            ],
            "steps": [
                [{"show": ["sentence", "subject", "omega_die", "array", "pointer", "note"]}],
                [{"highlight": ["omega.2", "array.0.2"]}],
                [{"set": "later", "to": "The mouse was chased."}],
            ],
        }
    )
    assert slide.left_out == []
    assert "[[True, '1'], [True, '2'], [True, '3']]" in slide.source
    assert "self.ring(['omega_die.2'], self.sun)" in slide.source
    assert "self.ring(['array.1.3'], self.sun)" in slide.source
    assert "\\subseteq" in slide.source


@pytest.mark.parametrize("kind", ["summary", "worked_example"])
def test_a_summary_or_a_worked_example_may_show_its_point_in_its_slide(kind: str) -> None:
    draft = copy.deepcopy(LESSON)
    draft["segments"][-1] = {
        "type": kind,
        "title": "In short",
        "problem": "Work out $2 + 3$." if kind == "worked_example" else None,
        "beats": [{"say": "It comes to [five]."}],
        "visual": {
            "elements": [{"id": "sum", "kind": "math", "tex": "2 + 3 = 5"}],
            "steps": [[{"show": "sum"}], [{"highlight": "sum"}]],
        },
    }
    compiled = compile_lesson(parse_lesson_draft(draft), CONTEXT)
    segment = compiled.lesson["segments"][-1]
    assert segment["type"] == kind
    assert "scene" in segment
    parse_bundle(
        {
            "lesson": compiled.lesson,
            "scenes": [],
            "pending_scene_ids": [figure.scene_id for figure in compiled.figures]
            + [brief.scene_id for brief in compiled.scenes],
        }
    )


def test_a_worked_example_without_a_problem_is_an_explanation() -> None:
    draft = copy.deepcopy(LESSON)
    draft["segments"][0] = {
        "type": "worked_example",
        "title": "Two and three",
        "beats": [{"say": "Two and three make [five]."}],
        "visual": {"elements": [{"id": "sum", "kind": "math", "tex": "2 + 3 = 5"}]},
    }
    compiled = compile_lesson(parse_lesson_draft(draft), CONTEXT)
    assert compiled.lesson["segments"][0]["type"] == "explanation"
    assert "problem" not in compiled.lesson["segments"][0]


# -- what thinking used to catch (ADR-049) ---------------------------------------------------


def test_a_wrong_option_that_is_the_right_one_written_another_way_is_left_out() -> None:
    from adle_core.generation.drafts import OptionDraft, _distinct_options

    options = [
        OptionDraft(text="3/52"),
        OptionDraft(text="12/52", correct=True),
        OptionDraft(text="1/4"),
        OptionDraft(text=r"$\frac{3}{13}$"),
        OptionDraft(text="23.08%"),
    ]
    assert [option.text for option in _distinct_options(options)] == [
        "3/52",
        "12/52",
        "1/4",
        "23.08%",
    ]
    # Options that are not numbers are left as they are.
    words = [OptionDraft(text="heads", correct=True), OptionDraft(text="tails")]
    assert _distinct_options(words) == words


@pytest.mark.parametrize(
    ("explanation", "answer", "worked"),
    [
        ("The sample space has 6 outcomes and the event 3, so 3/6 = 0.5.", 0.5, True),
        ("5 of the 36 pairs sum to 8: 5/36 ≈ 0.1389.", 0.139, True),
        (r"So the chance is $\frac{1}{4}$.", 0.25, True),
        ("Half of the outcomes are even.", 0.5, True),
        # A real answer written without thinking first (ADR-048): its key was 880.
        ("Multiply them out: 292,820. Wait, let me recheck: 292,820.", 880, False),
    ],
)
def test_a_numeric_key_is_what_its_own_working_finds(
    explanation: str, answer: float, worked: bool
) -> None:
    from adle_core.generation.drafts import _worked_to

    assert _worked_to(explanation, answer, None) is worked


def test_a_stage_with_no_places_puts_pictures_left_and_words_right() -> None:
    slide = compile_slide(
        {
            "elements": [
                {"id": "omega", "kind": "set", "items": ["H", "T"]},
                {"id": "rule", "kind": "math", "tex": "P(H) = \frac{1}{2}"},
            ]
        }
    )
    assert "self.put(['omega'], [-" in slide.source
    assert "self.put(['rule'], [" in slide.source
    assert "self.put(['omega', 'rule']" not in slide.source


# -- the case first, and the formula out of it (ADR-050) ---------------------------------------


def _step_of(source: str, number: int) -> str:
    """The lines of one step of a scene the module wrote."""
    start = source.index(f"    def step_{number}(self):")
    end = source.find("    def ", start + 10)
    return source[start : end if end > 0 else len(source)]


def test_a_formula_comes_out_of_the_picture_part_by_part() -> None:
    slide = compile_slide(visual_example()["visual"])
    built = _step_of(slide.source, 3)
    # The 3 and the 4 on the braces turn into the formula's parts; the rest is written in.
    assert "TransformFromCopy(self.e['h/name'], self.e['area'][0])" in built
    assert "TransformFromCopy(self.e['w/name'], self.e['area'][2])" in built
    assert "FadeIn(self.e['area'][1])" in built
    assert "FadeIn(self.e['area'][3])" in built
    # Then it is one formula on the stage again, which the next step turns into the rule.
    assert "self.remove(*self.e['area'].submobjects)" in built
    assert "self.add(self.e['area'])" in built
    assert "TransformMatchingTex(self.e['area'], self.e['rule'])" in _step_of(slide.source, 4)


def test_where_a_formula_s_parts_come_from_may_be_given_by_part() -> None:
    script = copy.deepcopy(EXAMPLES["counted_out"])
    script["steps"][2] = [{"show": "count", "from": {"count.2": "omega", "1": "event"}}]
    slide = compile_slide(script)
    assert slide.left_out == []
    built = _step_of(slide.source, 2)
    assert "TransformFromCopy(self.e['event/name'], self.e['count'][1])" in built
    assert "TransformFromCopy(self.group(['omega/frame'" in built
    assert "self.e['count'][3])" in built


@pytest.mark.parametrize(
    ("action", "said"),
    [
        ({"show": "count", "from": ["nowhere"]}, 'a "from" names "nowhere"'),
        ({"show": ["count", "rule"], "from": ["event"]}, "one element out of the picture"),
        ({"show": "omega", "from": ["event"]}, "a set does not come out of the picture"),
    ],
)
def test_a_from_that_cannot_be_followed_is_said_and_the_thing_is_shown_as_usual(
    action: dict[str, Any], said: str
) -> None:
    script = copy.deepcopy(EXAMPLES["counted_out"])
    script["steps"][2] = [action]
    slide = compile_slide(script)
    assert any(said in note for note in slide.left_out), slide.left_out
    built = _step_of(slide.source, 2)
    assert "TransformFromCopy" not in built


def test_the_case_comes_first_and_its_formula_waits_for_the_next_step() -> None:
    slide = compile_slide(EXAMPLES["case_first"])
    assert slide.steps == 2
    assert "self.e['odds']" not in _step_of(slide.source, 0).replace("self.e['odds'] =", "")
    first_play = next(
        line for line in _step_of(slide.source, 1).splitlines() if "self.play(" in line
    )
    assert "Write(self.e['odds'])" in first_play


def test_a_case_and_its_formula_shown_at_once_with_no_steps_become_two_steps() -> None:
    slide = compile_slide(
        {
            "elements": [
                {"id": "omega", "kind": "set", "items": ["H", "T"], "place": "left"},
                {"id": "rule", "kind": "math", "tex": "P(H) = \frac{1}{2}", "place": "right"},
            ]
        }
    )
    assert slide.steps == 2
    assert "Write(self.e['rule'])" in _step_of(slide.source, 1)


def test_a_slide_of_formulas_alone_keeps_its_first_step() -> None:
    slide = compile_slide(
        {
            "elements": [
                {"id": "a", "kind": "math", "tex": "2x + 3 = 7"},
                {"id": "b", "kind": "math", "tex": "2x = 4", "place": {"below": "a"}},
            ],
            "steps": [[{"show": ["a", "b"]}]],
        }
    )
    assert slide.steps == 1


def test_a_sentence_or_an_equation_comes_out_of_the_one_before_it() -> None:
    slide = compile_slide(EXAMPLES["rewritten"])
    assert "TransformMatchingTex(self.e['active'].copy(), self.e['passive'])" in _step_of(
        slide.source, 1
    )
    assert "TransformMatchingTex(self.e['first'].copy(), self.e['next'])" in _step_of(
        slide.source, 3
    )
    # The first of each is written as ever, and the one it came out of stays.
    assert "Write(self.e['active'])" in _step_of(slide.source, 0)
    assert "Write(self.e['first'])" in _step_of(slide.source, 2)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        # Only little words in common.
        ("The cat sat on the mat.", "The dog ran to the park."),
        # One word that says something, of seven.
        ("The cat sat.", "Then a big dog barked at the cat loudly."),
    ],
)
def test_a_sentence_that_shares_little_with_another_is_written_as_itself(
    first: str, second: str
) -> None:
    slide = compile_slide(
        {
            "elements": [
                {"id": "a", "kind": "words", "place": "top", "text": first},
                {"id": "b", "kind": "words", "place": "bottom", "text": second},
            ],
            "steps": [[{"show": "a"}], [{"show": "b"}]],
        }
    )
    assert "TransformMatchingTex" not in slide.source
    assert "Write(self.e['b'])" in _step_of(slide.source, 1)


def test_points_written_inline_are_points_of_their_own() -> None:
    """As a real model wrote them (2026-11-22): a tangent "at" a point written inline, or
    at a number on the one curve there is, and a line between two such points."""
    slide = compile_slide(EXAMPLES["tangents_inline"])
    assert slide.left_out == []
    for name in ("left_at", "flat_at", "secant_from", "secant_to"):
        assert f"self.make_point('{name}', 'axes', 0, " in slide.source


def test_numbers_follow_a_point_and_a_slider_that_moved_nothing_moves_the_point() -> None:
    slide = compile_slide(EXAMPLES["point_readouts"])
    assert slide.left_out == []
    assert slide.interactive
    # The point follows the slider now (no x of its own), and the numbers follow the point.
    assert "self.make_point('p', 'axes', 0, None, " in slide.source
    assert "self.value(1, self.trackers['p'].get_value()" in slide.source
    assert "self.value(2, self.trackers['p'].get_value()" in slide.source
    # Moved by {"x": ...}: set as a number would be.
    assert "set_value(2.0)" in slide.source or "set_value(2)" in slide.source


def test_a_number_s_formula_is_arithmetic_of_a_point_or_the_value_and_nothing_else() -> None:
    script = copy.deepcopy(EXAMPLES["point_readouts"])
    script["elements"][4]["value"] = "__import__('os').p.x"
    slide = compile_slide(script)
    assert any("which is not a number" in note for note in slide.left_out)
    assert "__import__" not in slide.source


# -- words kept clear of words, and of the edge (ADR-055) -------------------------------------------


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_every_slide_tidies_its_labels_before_it_shows_them_and_checks_each_step(
    name: str,
) -> None:
    slide = compile_slide(EXAMPLES[name])
    source = slide.source
    assert LAYOUT_METHODS in source
    build = source.split("    def build(self):")[1].split("\n    def ")[0]
    # Once everything is in place, and before the first step shows any of it.
    assert build.rstrip().endswith("self.tidy()")
    # Every step, and a live page, says how it is laid out as it ends: before its step.
    assert source.count('self.audit()\n        self.post_message("step"') == slide.steps


def test_a_line_through_a_word_counts_and_one_beside_it_does_not() -> None:
    # The methods every slide carries look for lines through words as well (ADR-056):
    # the lines that stay put are kept with the words that do, for a label to keep clear of,
    # and a step ends saying how many words a line runs through.
    assert "self.still_lines = lines" in LAYOUT_METHODS
    assert (
        "for line in self.still_lines:\n                if self.struck(m, line):" in LAYOUT_METHODS
    )
    assert '" under a line, "' in LAYOUT_METHODS
    # Only the middle of a word: a line that grazes it, or runs beside it, does not count.
    assert "+ 0.2 * w" in LAYOUT_METHODS
    assert "+ 0.25 * h" in LAYOUT_METHODS
    source = compile_slide(EXAMPLES["tangents_inline"]).source
    assert "self.still_lines = []" in source


def test_a_label_is_pinned_beside_what_it_names_unless_it_moves_with_it() -> None:
    source = compile_slide(EXAMPLES["tangent"]).source
    # The curve's name: pinned, so tidy may move it.
    assert "self.e['f/name'] = self.pin(self.shown([True, 'f(x)'], 28, self.blue)," in source
    # A point's name moves with the point: it keeps to a side clear of what stays put.
    assert "self.keep_clear(key, self.shown(name, 26, self.ink), dot, UP + RIGHT, 0.1)" in source


def test_a_label_on_something_that_moves_is_kept_clear_as_it_is_drawn() -> None:
    source = compile_slide(EXAMPLES["tangents_inline"]).source
    # "f' < 0" is beside a tangent that moves with its point: drawn again each frame, it
    # steps aside from the axis's numbers instead of lying over one (seen 2026-11-22).
    assert (
        "self.e['negative'] = always_redraw(lambda: self.keep_clear('negative', "
        "self.shown([False, \"f' < 0\"], 26, self.coral), self.group(['left']), LEFT, 0.14))"
    ) in source


# -- a step no longer than its words (ADR-055) ------------------------------------------------------

STEP = (
    "    def step_1(self):\n"
    "        self.play(FadeIn(self.e['a']), run_time=1.4)\n"
    "        self.play(self.amount.animate.set_value(2.5), run_time=2.0, rate_func=smooth)\n"
)


def test_a_step_with_time_to_spare_is_left_as_written() -> None:
    assert _fitted(STEP, None) == STEP
    assert _fitted(STEP, 3.4) == STEP
    assert _fitted(STEP, 30.0) == STEP


def test_a_step_with_less_time_than_its_animations_is_made_quicker() -> None:
    fitted = _fitted(STEP, 1.7)
    assert "run_time=0.7)" in fitted
    assert "run_time=1.0, rate_func=smooth)" in fitted


def test_a_step_is_never_made_too_quick_to_follow() -> None:
    fitted = _fitted(STEP, 0.2)
    # Down to 0.45 of what it was written to take, and no further.
    assert "run_time=0.63)" in fitted
    assert "run_time=0.9, rate_func=smooth)" in fitted


def test_each_step_has_until_the_next_one_begins() -> None:
    narration = _beats(
        ("The bar is three squares wide and four tall.", []),
        ("So it is twelve squares.", [3]),
    )
    first, last = _step_seconds(narration, 2)
    # Ten words briskly, and the pause between the lines.
    assert first == pytest.approx(10 / 3 + 0.3)
    # Four words, and a moment after the last of them.
    assert last == pytest.approx(4 / 3 + 0.6)
    assert _step_seconds([], 3) == []


def slide_written_for(beats: list[dict[str, Any]]) -> list[float]:
    """The run times in the slide of a part said in these words."""
    draft = copy.deepcopy(LESSON)
    draft["segments"][0] = {
        "type": "explanation",
        "title": "One flip",
        "beats": beats,
        "visual": copy.deepcopy(EXAMPLES["sample_space"])
        | {"steps": EXAMPLES["sample_space"]["steps"][:3]},
    }
    source = compile_lesson(parse_lesson_draft(draft), CONTEXT).figures[0].source
    return [float(value) for value in re.findall(r"run_time=(\d+(?:\.\d+)?)", source)]


def test_a_slide_whose_words_come_quickly_is_written_with_quicker_steps() -> None:
    unhurried = slide_written_for(
        [
            {"say": "Flip a coin. Think about every way it can land, slowly and with care."},
            {"say": "There are [two outcomes], heads and tails, and nothing else at all here."},
            {"say": "We call the outcome we care about [an event]; here it is heads."},
        ]
    )
    hurried = slide_written_for([{"say": "Flip a coin: [two] [outcomes]."}])
    assert len(hurried) == len(unhurried)
    assert sum(hurried) < sum(unhurried)
    # Quicker, and never too quick to follow.
    assert all(
        quick >= round(0.45 * slow, 2) for quick, slow in zip(hurried, unhurried, strict=True)
    )
