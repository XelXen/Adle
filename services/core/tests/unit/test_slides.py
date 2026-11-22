"""Slides (ADR-049): a part's picture as a script the model writes and the core draws,
paced by words of the narration marked in [brackets]."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from adle_core.generation.drafts import (
    LessonContext,
    ObjectiveRef,
    _cued,
    _marked,
    _paced,
    compile_lesson,
    parse_lesson_draft,
)
from adle_core.generation.figures import _cell
from adle_core.generation.prompts import visual_example
from adle_core.generation.scene_policy import check_scene_source
from adle_core.generation.slides import KINDS, VERBS, SlideError, compile_slide
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
