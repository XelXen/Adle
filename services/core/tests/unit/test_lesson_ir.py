"""The Lesson IR: what a lesson may contain, and what is refused."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from adle_core.generation.scene_policy import content_hash, pinned_wanim_version
from adle_core.learner_model.tracing import QUESTION_FORM_LABELS
from adle_core.lessons.bundle import (
    LessonInvalidError,
    SceneRejectedError,
    inspect_scene,
    parse_bundle,
)
from adle_core.lessons.ir import (
    QUESTION_FORMS,
    SCHEMA_VERSION,
    ChoiceItem,
    Lesson,
    LessonBundle,
    guess_probability,
)

EXAMPLES = Path(__file__).resolve().parents[4] / "skills" / "wanim-scene-authoring" / "examples"
ANIMATION = (EXAMPLES / "weighted_sum.py").read_text(encoding="utf-8")
INTERACTIVE = (EXAMPLES / "neuron_weight.py").read_text(encoding="utf-8")

COURSE = "crs_00000000000000000001"
CONCEPT = "con_00000000000000000001"
OBJECTIVE = "obj_00000000000000000001"


def choice(question_id: str = "q_which_input", **changes: Any) -> dict[str, Any]:
    return {
        "id": question_id,
        "form": "multiple_choice",
        "concept_id": CONCEPT,
        "objective_id": OBJECTIVE,
        "stem": "A neuron has weights $w_1 = 2$ and $w_2 = 0.1$. Which input matters more?",
        "options": [
            {"id": "a", "text": "The first input", "feedback": "Yes: its weight is larger."},
            {
                "id": "b",
                "text": "The second input",
                "feedback": "Its weight is much smaller.",
                "misconception": "definition_confusion",
            },
            {"id": "c", "text": "Both matter equally"},
        ],
        "correct_option": "a",
        "explanation": "The larger the weight, the more its input changes the sum.",
        "hint": "Compare the two weights.",
        "difficulty": 1,
        **changes,
    }


def lesson(**changes: Any) -> dict[str, Any]:
    """A complete, valid lesson that uses every kind of segment."""
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "lesson_id": "les_00000000000000000001",
        "course_id": COURSE,
        "title": "A single neuron",
        "concept_ids": [CONCEPT],
        "objectives": [
            {"objective_id": OBJECTIVE, "statement": "Compute the output of a neuron by hand."}
        ],
        "source_refs": [],
        "grounding": "sample",
        "strategy": "visual",
        "estimated_minutes": 6,
        "segments": [
            {
                "id": "seg_idea",
                "type": "explanation",
                "title": "What a neuron does",
                "estimated_seconds": 40,
                "narration": [
                    {
                        "text": "A neuron multiplies each input by a weight and adds the results.",
                        "show": "Output $= w_1 x_1 + w_2 x_2 + b$",
                    },
                    {"text": "The bias is added at the end, whatever the inputs are."},
                ],
            },
            {
                "id": "seg_picture",
                "type": "visualization",
                "title": "The weighted sum, drawn",
                "estimated_seconds": 30,
                "narration": [{"text": "Watch each input being scaled by its weight."}],
                "scene": {
                    "scene_id": "scn_weighted_sum",
                    "fallback_text": "Two inputs are each multiplied by a weight and added.",
                },
            },
            {
                "id": "seg_try",
                "type": "interaction",
                "title": "Change a weight",
                "estimated_seconds": 60,
                "prompt": "Drag the weight and watch how much the first input counts.",
                "scene": {
                    "scene_id": "scn_neuron_weight",
                    "fallback_text": "A larger weight makes the bar for that input taller.",
                },
            },
            {
                "id": "seg_check",
                "type": "checkpoint",
                "title": "Check",
                "estimated_seconds": 30,
                "question": choice(),
            },
            {
                "id": "seg_worked",
                "type": "worked_example",
                "title": "By hand",
                "estimated_seconds": 60,
                "problem": "Inputs $x = (1, 2)$, weights $w = (0.5, -1)$, bias $b = 1$.",
                "narration": [
                    {"text": "Half of one is a half.", "show": "$0.5 \\cdot 1 = 0.5$"},
                    {"text": "Minus one times two is minus two.", "show": "$-1 \\cdot 2 = -2$"},
                    {"text": "Add them and the bias.", "show": "$0.5 - 2 + 1 = -0.5$"},
                ],
            },
            {
                "id": "seg_think",
                "type": "reflection",
                "title": "Think about it",
                "estimated_seconds": 30,
                "prompt": "What would a weight of zero mean for an input?",
            },
            {
                "id": "seg_recap",
                "type": "summary",
                "title": "In short",
                "estimated_seconds": 20,
                "narration": [
                    {
                        "text": "A neuron is a weighted sum plus a bias.",
                        "show": "Weighted sum + bias",
                    }
                ],
            },
        ],
    }
    base.update(changes)
    return base


def bundle(**lesson_changes: Any) -> dict[str, Any]:
    return {
        "lesson": lesson(**lesson_changes),
        "scenes": [
            {"id": "scn_weighted_sum", "purpose": "Show a weighted sum.", "source": ANIMATION},
            {
                "id": "scn_neuron_weight",
                "purpose": "Let a weight be changed.",
                "source": INTERACTIVE,
            },
        ],
    }


def problems(data: dict[str, Any]) -> list[tuple[str, str]]:
    with pytest.raises(LessonInvalidError) as raised:
        parse_bundle(data)
    return [(problem.where, problem.message) for problem in raised.value.problems]


def edited(path: list[Any], value: Any) -> dict[str, Any]:
    """A valid bundle with one value replaced, e.g. ``["lesson", "segments", 0, "title"]``."""
    data = bundle()
    target: Any = data
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return data


# -- the valid lesson -------------------------------------------------------


def test_a_complete_lesson_is_accepted_and_survives_being_stored() -> None:
    parsed = parse_bundle(bundle())
    assert parsed.lesson.title == "A single neuron"
    assert [segment.type for segment in parsed.lesson.segments] == [
        "explanation",
        "visualization",
        "interaction",
        "checkpoint",
        "worked_example",
        "reflection",
        "summary",
    ]
    assert parsed.lesson.scene_ids() == ["scn_weighted_sum", "scn_neuron_weight"]
    assert [question.id for question in parsed.lesson.questions()] == ["q_which_input"]

    stored = parsed.model_dump(mode="json")
    assert LessonBundle.model_validate(stored) == parsed
    # The stored form can be parsed again as input: the scene descriptions are simply recomputed.
    assert parse_bundle(stored) == parsed


def test_the_question_forms_match_the_ones_the_learner_model_understands() -> None:
    assert set(QUESTION_FORMS) == set(QUESTION_FORM_LABELS)


# -- scenes are never taken on trust ----------------------------------------


def test_a_scene_is_described_from_its_source_not_from_what_the_input_claims() -> None:
    data = bundle()
    data["scenes"][0].update(
        {
            "interactive": True,
            "controls": ["anything"],
            "content_hash": "f" * 64,
            "scene_class": "NotTheRealName",
            "wanim_version": "99.0.0",
        }
    )
    scene = parse_bundle(data).scenes[0]
    assert scene.interactive is False
    assert scene.controls == []
    assert scene.scene_class == "WeightedSum"
    assert scene.content_hash == content_hash(ANIMATION)
    assert scene.wanim_version == pinned_wanim_version()

    interactive = parse_bundle(data).scenes[1]
    assert interactive.interactive is True
    assert interactive.controls == ["weight", "bias_on"]
    assert set(interactive.events) == {"explored", "passed"}


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("import os\nfrom manim import *\n\nclass A(Scene):\n    pass\n", "forbidden_import"),
        (
            "from manim import *\n\nclass A(Scene):\n    def construct(self):\n        fetch('x')\n",
            "unknown_name",
        ),
        ("class Broken(Scene:\n    pass\n", "syntax_error"),
        ("", "empty"),
    ],
)
def test_a_scene_that_breaks_the_policy_rejects_the_whole_lesson(source: str, code: str) -> None:
    data = bundle()
    data["scenes"][0]["source"] = source
    with pytest.raises(SceneRejectedError) as raised:
        parse_bundle(data)
    assert raised.value.scene_id == "scn_weighted_sum"
    assert code in {violation.code for violation in raised.value.violations}
    # The learner is told what happened, not shown the code.
    assert "fetch" not in raised.value.message
    assert raised.value.detail["scene_id"] == "scn_weighted_sum"


def test_a_scene_file_defines_exactly_one_scene() -> None:
    two = ANIMATION + "\n\nclass Second(Scene):\n    def construct(self):\n        self.wait(0.1)\n"
    with pytest.raises(SceneRejectedError) as raised:
        inspect_scene("scn_two", "Two scenes.", two)
    assert [violation.code for violation in raised.value.violations] == ["one_scene_per_file"]


def test_every_scene_reference_must_resolve_and_every_scene_must_be_used() -> None:
    missing = bundle()
    missing["scenes"].pop(0)
    assert ("lesson", "segment seg_picture refers to a scene that is not included") in problems(
        missing
    )

    unused = bundle()
    unused["scenes"].append({"id": "scn_spare", "purpose": "Not used.", "source": ANIMATION})
    assert ("lesson", "a scene is included that no segment uses") in problems(unused)

    repeated = bundle()
    repeated["scenes"].append(dict(repeated["scenes"][0]))
    assert ("lesson", "scene ids must be different") in problems(repeated)


def test_an_interaction_needs_a_scene_with_something_to_interact_with() -> None:
    data = edited(["lesson", "segments", 2, "scene", "scene_id"], "scn_weighted_sum")
    data["scenes"].pop(1)
    assert problems(data) == [
        (
            "lesson",
            "segment seg_try is an interaction but its scene has nothing to interact with",
        )
    ]


@pytest.mark.parametrize(
    "scenes",
    [
        "not a list",
        ["not an object"],
        [{"id": "scn_x", "purpose": "No source."}],
        [{"id": 7, "purpose": "Bad id.", "source": ANIMATION}],
        [{"id": "Scene One", "purpose": "Bad id.", "source": ANIMATION}],
    ],
)
def test_malformed_scene_entries_are_refused(scenes: Any) -> None:
    data = bundle()
    data["scenes"] = scenes
    with pytest.raises(LessonInvalidError):
        parse_bundle(data)


def test_something_that_is_not_a_lesson_at_all_is_refused() -> None:
    for junk in (None, [], "lesson", 7, {"lesson": None}, {}):
        with pytest.raises(LessonInvalidError):
            parse_bundle(junk)


# -- strict shape -----------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ["lesson", "html"],
        ["lesson", "segments", 0, "component"],
        ["lesson", "segments", 0, "narration", 0, "audio_url"],
        ["lesson", "segments", 1, "scene", "source"],
        ["lesson", "segments", 3, "question", "options", 0, "correct"],
        ["lesson", "objectives", 0, "weight"],
    ],
)
def test_unknown_fields_are_rejected_at_every_level(path: list[Any]) -> None:
    found = problems(edited(path, "x"))
    assert len(found) == 1
    assert found[0][1] == "Extra inputs are not permitted"
    assert found[0][0].endswith(str(path[-1]))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["lesson", "schema_version"], "2.0"),
        (["lesson", "segments", 0, "type"], "video"),
        (["lesson", "segments", 3, "question", "form"], "essay"),
        (["lesson", "strategy"], "hypnosis"),
        (["lesson", "grounding"], "the internet"),
        (["lesson", "lesson_id"], "lesson one"),
        (["lesson", "concept_ids"], []),
        (["lesson", "segments"], []),
        (["lesson", "segments", 0, "id"], "Segment 1"),
        (["lesson", "segments", 0, "estimated_seconds"], 0),
        (["lesson", "segments", 0, "estimated_seconds"], 100_000),
        (["lesson", "segments", 0, "narration"], []),
        (["lesson", "segments", 0, "title"], "   "),
        (["lesson", "estimated_minutes"], 500),
    ],
)
def test_values_outside_the_contract_are_rejected(path: list[Any], value: Any) -> None:
    assert problems(edited(path, value))


# -- text is plain, bounded, and free of anything that looks executable ------


@pytest.mark.parametrize(
    "text",
    [
        "Read more at https://example.com/lesson",
        "See www.example.com for details",
        "Open file:///etc/passwd",
        "Click javascript:alert(1)",
        "Use data:text/html;base64,AAAA",
        "<script>alert(1)</script>",
        "Look: <img src=x onerror=alert(1)>",
        '<a href="x">here</a>',
        "A line<br>break",
        "<p>Paragraph</p>",
        "Saved in C:\\Users\\learner\\notes",
        "Run cat /etc/passwd",
        "Go to ../secrets",
        "Bell" + chr(7) + "character",
    ],
)
@pytest.mark.parametrize(
    "path",
    [
        ["lesson", "title"],
        ["lesson", "segments", 0, "narration", 0, "text"],
        ["lesson", "segments", 0, "narration", 0, "show"],
        ["lesson", "segments", 1, "scene", "fallback_text"],
        ["lesson", "segments", 3, "question", "stem"],
        ["lesson", "segments", 3, "question", "options", 0, "text"],
        ["lesson", "segments", 3, "question", "explanation"],
    ],
)
def test_links_markup_paths_and_control_characters_are_refused(path: list[Any], text: str) -> None:
    found = problems(edited(path, text))
    assert found, text
    # The report says what is wrong without repeating the text.
    for _where, message in found:
        assert "alert" not in message
        assert "example.com" not in message
        assert "passwd" not in message


@pytest.mark.parametrize(
    "text",
    [
        "Consider this data: 2, 4, and 6.",
        "If x < a and y > 3, the neuron fires.",
        "The ratio is 3:1, so a < b.",
        "Use the file: it lists every weight.",
        "A function $f:\\mathbb{R}\\to\\mathbb{R}$ maps numbers to numbers.",
        "Compute $a/b$ and then $c/d$.",
        "Either/or: pick one.",
        "This costs about 5 dollars a day in compute, roughly.",
    ],
)
def test_ordinary_prose_and_mathematics_are_not_mistaken_for_something_dangerous(text: str) -> None:
    parsed = parse_bundle(edited(["lesson", "segments", 3, "question", "stem"], text))
    assert parsed.lesson.questions()[0].stem == text


def test_narration_is_words_and_display_text_may_carry_closed_mathematics() -> None:
    notation = problems(
        edited(["lesson", "segments", 0, "narration", 0, "text"], "Compute $w \\cdot x$ now.")
    )
    assert "write mathematics in words" in notation[0][1]

    unclosed = problems(edited(["lesson", "segments", 0, "narration", 0, "show"], "Then $x = 2"))
    assert "closed with a second dollar sign" in unclosed[0][1]

    too_long = problems(edited(["lesson", "segments", 0, "narration", 0, "text"], "word " * 400))
    assert too_long[0][0] == "lesson.segments.0.explanation.narration.0.text"


# -- segments ---------------------------------------------------------------


def test_each_kind_of_segment_has_what_it_needs() -> None:
    no_scene = bundle()
    del no_scene["lesson"]["segments"][1]["scene"]
    assert problems(no_scene)[0][1] == "Field required"

    silent_steps = bundle()
    for beat in silent_steps["lesson"]["segments"][4]["narration"]:
        beat.pop("show")
    assert problems(silent_steps)[0][1] == "a worked example must show at least one step"

    no_points = bundle()
    no_points["lesson"]["segments"][6]["narration"][0].pop("show")
    assert problems(no_points)[0][1] == "a summary must show at least one key point"

    no_question = bundle()
    del no_question["lesson"]["segments"][3]["question"]
    assert problems(no_question)[0][1] == "Field required"


def test_a_lesson_is_coherent_as_a_whole() -> None:
    twice = bundle()
    twice["lesson"]["segments"][5]["id"] = "seg_idea"
    assert ("lesson", "segment ids must be different") in problems(twice)

    data = bundle()
    data["lesson"]["segments"].append(
        {
            "id": "seg_check_again",
            "type": "checkpoint",
            "title": "Again",
            "estimated_seconds": 20,
            "question": choice(),
        }
    )
    assert ("lesson", "question ids must be different") in problems(data)

    elsewhere = edited(
        ["lesson", "segments", 3, "question", "concept_id"], "con_000000000000000000ff"
    )
    assert (
        "lesson",
        "question q_which_input is about a concept this lesson does not teach",
    ) in problems(elsewhere)

    uncited = bundle(grounding="materials")
    assert (
        "lesson",
        "a lesson grounded in the learner's materials must cite them",
    ) in problems(uncited)

    cited = bundle(
        grounding="materials",
        source_refs=[
            {
                "source_id": "src_00000000000000000001",
                "section_id": "sec_00000000000000000001",
                "source_name": "lecture-notes.pdf",
                "locator": "page 2",
            }
        ],
    )
    assert parse_bundle(cited).lesson.source_refs[0].locator == "page 2"

    marathon = bundle()
    for segment in marathon["lesson"]["segments"]:
        segment["estimated_seconds"] = 900
    assert ("lesson", "a lesson cannot be longer than an hour") in problems(marathon)


# -- questions --------------------------------------------------------------


def question_bundle(question: dict[str, Any]) -> dict[str, Any]:
    return edited(["lesson", "segments", 3, "question"], question)


def base_item(form: str, **fields: Any) -> dict[str, Any]:
    return {
        "id": "q_item",
        "form": form,
        "concept_id": CONCEPT,
        "stem": "A question?",
        "explanation": "Because.",
        **fields,
    }


@pytest.mark.parametrize(
    "question",
    [
        choice(form="prediction"),
        base_item("true_false", correct=False),
        base_item("numeric", expected=-0.5, tolerance=0.01, unit="V"),
        base_item("short_answer", accepted=["bias", "the bias"]),
        base_item(
            "ordering",
            items=[
                {"id": "a", "text": "Multiply inputs by weights"},
                {"id": "b", "text": "Add the bias"},
                {"id": "c", "text": "Apply the activation"},
            ],
        ),
        base_item(
            "explanation",
            rubric=[
                {"id": "sum", "text": "Mentions the weighted sum"},
                {"id": "bias", "text": "Mentions the bias"},
            ],
            required_points=2,
            sample_answer="It multiplies inputs by weights, adds them, and adds a bias.",
        ),
    ],
)
def test_every_question_form_is_accepted(question: dict[str, Any]) -> None:
    parsed = parse_bundle(question_bundle(question))
    assert parsed.lesson.questions()[0].form == question["form"]


@pytest.mark.parametrize(
    ("question", "message"),
    [
        (choice(correct_option="z"), "correct_option must be one of the options"),
        (
            choice(options=[{"id": "a", "text": "Yes"}, {"id": "a", "text": "No"}]),
            "option ids must be different",
        ),
        (
            choice(options=[{"id": "a", "text": "Same"}, {"id": "b", "text": "same"}]),
            "two options say the same thing",
        ),
        (choice(options=[{"id": "a", "text": "Only one"}]), "List should have at least 2 items"),
        (
            base_item("numeric", expected=float("inf")),
            "expected and tolerance must be finite numbers",
        ),
        (
            base_item("numeric", expected=1, tolerance=-1),
            "Input should be greater than or equal to 0",
        ),
        (base_item("short_answer", accepted=[]), "List should have at least 1 item"),
        (
            base_item(
                "ordering",
                items=[
                    {"id": "a", "text": "A"},
                    {"id": "b", "text": "a"},
                    {"id": "c", "text": "C"},
                ],
            ),
            "ordering items must be different from each other",
        ),
        (
            base_item(
                "explanation",
                rubric=[{"id": "a", "text": "One point"}],
                required_points=3,
                sample_answer="An answer.",
            ),
            "required_points cannot exceed the number of rubric points",
        ),
        (base_item("true_false", correct="maybe"), "Input should be a valid boolean"),
    ],
)
def test_incoherent_questions_are_rejected(question: dict[str, Any], message: str) -> None:
    found = [text for _where, text in problems(question_bundle(question))]
    assert any(message in text for text in found), found


def test_guessing_odds_depend_on_the_form_of_the_question() -> None:
    lesson_model = Lesson.model_validate(lesson())
    multiple_choice = lesson_model.questions()[0]
    assert isinstance(multiple_choice, ChoiceItem)
    assert guess_probability(multiple_choice) == pytest.approx(1 / 3)

    def parsed(question: dict[str, Any]) -> Any:
        return parse_bundle(question_bundle(question)).lesson.questions()[0]

    assert guess_probability(parsed(base_item("true_false", correct=True))) == 0.5
    assert guess_probability(parsed(base_item("numeric", expected=2))) == 0.02
    ordering = base_item(
        "ordering",
        items=[{"id": key, "text": key.upper()} for key in ("a", "b", "c", "d")],
    )
    assert guess_probability(parsed(ordering)) == pytest.approx(1 / 24)


def test_a_valid_lesson_cannot_be_changed_after_validation() -> None:
    parsed = parse_bundle(bundle())
    with pytest.raises(Exception, match="frozen"):
        parsed.lesson.title = "Changed"  # type: ignore[misc]
    assert copy.deepcopy(parsed) == parsed
