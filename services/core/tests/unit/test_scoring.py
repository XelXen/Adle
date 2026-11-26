"""Scoring closed questions: one written-down rule per form."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter

from adle_core.evaluation.scoring import (
    MalformedResponseError,
    Response,
    near_miss,
    normalise_answer,
    score,
)
from adle_core.learner_model.bkt import Outcome
from adle_core.lessons.ir import AssessmentItem
from adle_core.lessons.player import ItemMask, player_question

CONCEPT = "con_00000000000000000001"
_ITEM = TypeAdapter(AssessmentItem)


def item(form: str, **fields: Any) -> Any:
    return _ITEM.validate_python(
        {
            "id": "q_item",
            "form": form,
            "concept_id": CONCEPT,
            "stem": "A question?",
            "explanation": "Because.",
            **fields,
        }
    )


CHOICE = item(
    "multiple_choice",
    options=[
        {"id": "a", "text": "Right", "feedback": "Yes, exactly."},
        {
            "id": "b",
            "text": "Tempting",
            "feedback": "That mixes up two terms.",
            "misconception": "definition_confusion",
        },
        {"id": "c", "text": "Wrong"},
    ],
    correct_option="a",
)
NUMERIC = item("numeric", expected=-0.5, tolerance=0.01, unit="V")
SHORT = item("short_answer", accepted=["Bias", "the bias term"])
#: What only the core has. Another installation has another.
MASK = ItemMask(b"a secret that never leaves the core")

ORDERING = item(
    "ordering",
    items=[
        {"id": "a", "text": "Multiply"},
        {"id": "b", "text": "Add"},
        {"id": "c", "text": "Add the bias"},
        {"id": "d", "text": "Activate"},
    ],
)
EXPLANATION = item(
    "explanation",
    rubric=[
        {"id": "sum", "text": "Mentions the weighted sum"},
        {"id": "bias", "text": "Mentions the bias"},
        {"id": "act", "text": "Mentions the activation"},
    ],
    required_points=2,
    sample_answer="Multiply, add, add the bias, activate.",
)


# -- choices ----------------------------------------------------------------


def test_a_choice_is_right_or_wrong_and_says_something_about_what_was_chosen() -> None:
    right = score(CHOICE, Response(option_id="a"))
    assert (right.outcome, right.feedback, right.misconception) == (
        Outcome.CORRECT,
        "Yes, exactly.",
        None,
    )
    tempting = score(CHOICE, Response(option_id="b"))
    assert tempting.outcome is Outcome.INCORRECT
    assert tempting.feedback == "That mixes up two terms."
    # A suggestion about the kind of mistake, carried as a hypothesis.
    assert tempting.misconception == "definition_confusion"
    assert tempting.correct_answer == "Right"
    # The right option is named too, so it can be marked among the options on screen.
    assert (right.correct_option, tempting.correct_option) == ("a", "a")
    plain = score(CHOICE, Response(option_id="c"))
    assert (plain.outcome, plain.feedback, plain.misconception) == (Outcome.INCORRECT, None, None)


def test_true_or_false() -> None:
    statement = item("true_false", correct=False)
    assert score(statement, Response(truth=False)).outcome is Outcome.CORRECT
    wrong = score(statement, Response(truth=True))
    assert (wrong.outcome, wrong.correct_answer, wrong.correct_option) == (
        Outcome.INCORRECT,
        "False",
        "false",
    )


# -- numbers ----------------------------------------------------------------


@pytest.mark.parametrize("value", [-0.5, -0.49, -0.51, -0.5000001])
def test_a_number_within_the_tolerance_is_correct(value: float) -> None:
    result = score(NUMERIC, Response(number=value))
    assert result.outcome is Outcome.CORRECT
    assert result.correct_answer == "-0.5 V"
    # A question without options has no option to point at.
    assert result.correct_option is None


@pytest.mark.parametrize("value", [-0.52, 0.0, 5.0, -50.0])
def test_a_number_outside_the_tolerance_is_not(value: float) -> None:
    assert score(NUMERIC, Response(number=value)).outcome is Outcome.INCORRECT


def test_floating_point_noise_does_not_fail_an_exact_answer() -> None:
    exact = item("numeric", expected=0.3)
    assert score(exact, Response(number=0.1 + 0.2)).outcome is Outcome.CORRECT
    whole = item("numeric", expected=3)
    assert score(whole, Response(number=3.0)).correct_answer == "3"
    assert score(whole, Response(number=3.001)).outcome is Outcome.INCORRECT


def test_the_right_size_with_the_wrong_sign_is_flagged_as_a_likely_slip() -> None:
    flipped = score(NUMERIC, Response(number=0.5))
    assert flipped.outcome is Outcome.INCORRECT
    assert flipped.misconception == "arithmetic_slip"
    assert score(NUMERIC, Response(number=2.0)).misconception is None
    # Zero has no sign to get wrong.
    assert score(item("numeric", expected=0), Response(number=0.5)).misconception is None


# -- short answers ----------------------------------------------------------


@pytest.mark.parametrize(
    "given", ["bias", "  The Bias ", "BIAS.", "the bias term", "a bias", "Bias!"]
)
def test_short_answers_ignore_case_spacing_punctuation_and_articles(given: str) -> None:
    assert score(SHORT, Response(text=given)).outcome is Outcome.CORRECT


@pytest.mark.parametrize("given", ["weight", "biased estimate", "bias and weight"])
def test_other_short_answers_are_incorrect(given: str) -> None:
    result = score(SHORT, Response(text=given))
    assert (result.outcome, result.correct_answer) == (Outcome.INCORRECT, "Bias")


CHEMISTRY = item("short_answer", accepted=["CH3CH2CH3", "propane"])


@pytest.mark.parametrize(
    ("given", "near"),
    [
        # A key slipped (ADR-078): one changed, put in, left out, or two swapped.
        ("CH3CHWCH3", True),
        ("CH3CH2CH33", True),
        ("CH3CH2H3", True),
        ("CH3HC2CH3", True),
        ("propnae", True),
        # Two slips in an answer of fewer than ten characters, or more than two in any.
        ("CH3CWWCH3", False),
        ("butane", False),
        # Right, or nothing like it.
        ("CH3CH2CH3", False),
        ("ethanol", False),
    ],
)
def test_a_slip_of_the_keys_is_a_near_miss(given: str, near: bool) -> None:
    assert near_miss(CHEMISTRY, Response(text=given)) is near


def test_a_short_answer_or_a_number_has_no_near_miss() -> None:
    # Where one character is the whole difference, a slip and a wrong answer are one thing.
    assert not near_miss(item("short_answer", accepted=["CH4"]), Response(text="CH3"))
    assert not near_miss(item("short_answer", accepted=["1024"]), Response(text="1025"))
    # Ten characters or more allow two slips.
    long = item("short_answer", accepted=["photosynthesis"])
    assert near_miss(long, Response(text="photosinthesys"))
    assert not near_miss(long, Response(text="fotosinthesys"))
    # Only typed answers: a choice has nothing to slip on.
    assert not near_miss(item("true_false", correct=True), Response(truth=False))


def test_normalising_keeps_what_distinguishes_answers() -> None:
    assert normalise_answer("  The   Chain-Rule. ") == "chain-rule"
    assert normalise_answer("Résumé") == "resume"
    assert normalise_answer("1/2") == "1/2"
    assert normalise_answer("3.5") == "3.5"
    assert normalise_answer("An x+y") == "x+y"


# -- ordering ---------------------------------------------------------------


def test_an_order_is_correct_nearly_correct_or_not() -> None:
    assert score(ORDERING, Response(order=("a", "b", "c", "d"))).outcome is Outcome.CORRECT
    # One item out of place.
    near = score(ORDERING, Response(order=("b", "a", "c", "d")))
    assert (near.outcome, near.misconception) == (Outcome.PARTIAL, None)
    assert score(ORDERING, Response(order=("a", "c", "d", "b"))).outcome is Outcome.PARTIAL
    scrambled = score(ORDERING, Response(order=("d", "c", "b", "a")))
    assert (scrambled.outcome, scrambled.misconception) == (Outcome.INCORRECT, "procedure_order")
    assert scrambled.correct_answer == "Multiply; then Add; then Add the bias; then Activate"


# -- explanations -----------------------------------------------------------


def test_an_explanation_is_scored_from_the_rubric_points_and_marked_as_self_assessed() -> None:
    full = score(EXPLANATION, Response(covered=("sum", "bias")))
    assert (full.outcome, full.self_assessed) == (Outcome.CORRECT, True)
    assert score(EXPLANATION, Response(covered=("act",))).outcome is Outcome.PARTIAL
    none = score(EXPLANATION, Response(covered=()))
    assert (none.outcome, none.self_assessed) == (Outcome.INCORRECT, True)
    assert none.correct_answer == "Multiply, add, add the bias, activate."


# -- responses that do not fit ----------------------------------------------


@pytest.mark.parametrize(
    ("question", "response"),
    [
        (CHOICE, Response(option_id="z")),
        (CHOICE, Response()),
        (CHOICE, Response(number=1.0)),
        (item("true_false", correct=True), Response(option_id="a")),
        (NUMERIC, Response(text="minus a half")),
        (NUMERIC, Response(number=float("nan"))),
        (NUMERIC, Response(number=float("inf"))),
        (SHORT, Response(text="   ")),
        (SHORT, Response(text="x" * 401)),
        (ORDERING, Response(order=("a", "b", "c"))),
        (ORDERING, Response(order=("a", "a", "b", "c"))),
        (ORDERING, Response(order=("a", "b", "c", "z"))),
        (EXPLANATION, Response(covered=("sum", "sum"))),
        (EXPLANATION, Response(covered=("invented",))),
        (EXPLANATION, Response(text="My explanation")),
    ],
)
def test_a_response_that_does_not_fit_the_question_is_refused_not_marked_wrong(
    question: Any, response: Response
) -> None:
    with pytest.raises(MalformedResponseError):
        score(question, response)


# -- what the player is given -----------------------------------------------


def test_the_player_never_receives_an_answer_key() -> None:
    for question in (CHOICE, NUMERIC, SHORT, ORDERING, item("true_false", correct=True)):
        shown = player_question(question, "les_00000000000000000001", MASK).model_dump()
        assert "correct_option" not in shown
        assert "correct" not in shown
        assert "expected" not in shown
        assert "accepted" not in shown
        assert "explanation" not in shown
        text = str(shown)
        assert "Yes, exactly." not in text
        assert "definition_confusion" not in text
        assert "the bias term" not in text
    assert player_question(NUMERIC, "les_x", MASK).unit == "V"


def test_options_are_shuffled_the_same_way_every_time() -> None:
    lesson = "les_00000000000000000001"
    first = [option.id for option in player_question(CHOICE, lesson, MASK).options]
    assert sorted(first) == ["a", "b", "c"]
    assert [option.id for option in player_question(CHOICE, lesson, MASK).options] == first
    # A different lesson shuffles differently often enough to matter.
    orders = {
        tuple(option.id for option in player_question(CHOICE, f"les_{index:020d}", MASK).options)
        for index in range(30)
    }
    assert len(orders) > 1


def test_items_to_order_are_never_shown_already_in_order() -> None:
    in_order = [entry.text for entry in ORDERING.items]
    for index in range(60):
        shown = player_question(ORDERING, f"les_{index:020d}", MASK).options
        assert sorted(option.text for option in shown) == sorted(in_order)
        assert [option.text for option in shown] != in_order


def test_the_items_of_an_ordering_question_are_shown_under_names_that_are_not_the_answer() -> None:
    """A lesson's own ids for them are given in the right order, so they are the answer."""
    correct = ("a", "b", "c", "d")
    for index in range(60):
        lesson = f"les_{index:020d}"
        shown = player_question(ORDERING, lesson, MASK).options
        names = [option.id for option in shown]
        assert not set(names) & set(correct)
        # Sorting the names is no help: that is the order they are already shown in,
        # and it is never the right one.
        assert names == sorted(names)
        assert [option.text for option in shown] != [entry.text for entry in ORDERING.items]
        # Only the core can turn them back, to the same items every time.
        by_text = {option.text: option.id for option in shown}
        right = [by_text[entry.text] for entry in ORDERING.items]
        assert MASK.real(lesson, ORDERING, right) == correct
        assert score(ORDERING, Response(order=MASK.real(lesson, ORDERING, right))).outcome is (
            Outcome.CORRECT
        )
        # The same names again after a reload.
        assert [option.id for option in player_question(ORDERING, lesson, MASK).options] == names


def test_an_items_own_id_or_a_name_from_elsewhere_is_not_accepted_as_its_name() -> None:
    lesson = "les_00000000000000000001"
    names = [option.id for option in player_question(ORDERING, lesson, MASK).options]
    # The ids themselves, in order: what a page would send if it had read them.
    assert MASK.real(lesson, ORDERING, ["a", "b", "c", "d"]) == ("", "", "", "")
    with pytest.raises(MalformedResponseError):
        score(ORDERING, Response(order=MASK.real(lesson, ORDERING, ["a", "b", "c", "d"])))
    # Names made for another lesson, or with another installation's secret.
    assert set(MASK.real("les_00000000000000000002", ORDERING, names)) == {""}
    elsewhere = ItemMask(b"the secret of another installation")
    assert set(elsewhere.real(lesson, ORDERING, names)) == {""}
    assert not set(names) & {
        option.id for option in player_question(ORDERING, lesson, elsewhere).options
    }


def test_a_mask_needs_a_real_secret_and_never_shows_it() -> None:
    with pytest.raises(ValueError, match="too short"):
        ItemMask(b"short")
    assert "never leaves" not in repr(MASK)


def test_an_explanation_question_carries_what_the_learner_compares_against() -> None:
    shown = player_question(EXPLANATION, "les_00000000000000000001", MASK)
    assert [point.id for point in shown.rubric] == ["sum", "bias", "act"]
    assert shown.sample_answer == "Multiply, add, add the bias, activate."
    assert shown.options == []
