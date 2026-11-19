"""Learner preferences: explicit choices, safe defaults, tolerant loading."""

from __future__ import annotations

import pytest

from adle_core.learner_model.preferences import (
    DEFAULT_PREFERENCES,
    MAX_GOAL_LENGTH,
    PREFERENCE_KEYS,
    ExplanationDensity,
    LearnerPreferences,
    Pace,
    from_stored,
)


def test_defaults_suit_someone_who_has_not_chosen_anything() -> None:
    assert (
        LearnerPreferences(
            pace=Pace.STANDARD,
            explanation_density=ExplanationDensity.BALANCED,
            narration=True,
            captions=True,
            goal="",
            voice="",
            volume=100,
        )
        == DEFAULT_PREFERENCES
    )
    assert from_stored({}) == DEFAULT_PREFERENCES


def test_preferences_survive_being_stored_and_loaded() -> None:
    chosen = LearnerPreferences(
        pace=Pace.RELAXED,
        explanation_density=ExplanationDensity.DETAILED,
        narration=False,
        captions=True,
        goal="Understand backpropagation well enough to implement it.",
    )
    stored = chosen.to_stored()
    assert set(stored) == set(PREFERENCE_KEYS)
    assert stored["pace"] == "relaxed"
    assert stored["narration"] is False
    assert from_stored(stored) == chosen


@pytest.mark.parametrize(
    "stored",
    [
        {"pace": "warp speed"},
        {"pace": 3},
        {"explanation_density": None},
        {"narration": "yes"},
        {"captions": 1},
        {"goal": ["not", "text"]},
        {"something_from_a_newer_version": True},
    ],
)
def test_values_that_cannot_be_used_fall_back_to_the_default(stored: dict[str, object]) -> None:
    assert from_stored(stored) == DEFAULT_PREFERENCES


def test_one_bad_value_does_not_discard_the_others() -> None:
    loaded = from_stored({"pace": "brisk", "narration": "maybe", "captions": False})
    assert loaded.pace is Pace.BRISK
    assert loaded.narration is True
    assert loaded.captions is False


def test_a_goal_is_tidied_and_bounded() -> None:
    loaded = from_stored({"goal": "  pass   the\nexam  " + "x" * 1000})
    assert loaded.goal.startswith("pass the exam ")
    assert len(loaded.goal) == MAX_GOAL_LENGTH
    with pytest.raises(ValueError, match="at most"):
        LearnerPreferences(goal="y" * (MAX_GOAL_LENGTH + 1))


def test_a_voice_and_a_volume_are_kept_and_nonsense_is_ignored() -> None:
    chosen = LearnerPreferences(voice="Microsoft Zira - English (United States)", volume=40)
    assert from_stored(chosen.to_stored()) == chosen
    # A stored value of the wrong kind falls back to the default, like any other preference.
    for stored in (
        {"voice": 7},
        {"voice": "v" * 500},
        {"volume": "loud"},
        {"volume": 400},
        {"volume": True},
        {"volume": -5},
    ):
        assert from_stored(stored) == DEFAULT_PREFERENCES, stored


def test_a_volume_outside_the_scale_is_refused() -> None:
    import pytest

    with pytest.raises(ValueError, match="0 to 100"):
        LearnerPreferences(volume=101)
    with pytest.raises(ValueError, match="voice"):
        LearnerPreferences(voice="v" * 121)
