"""The Expressive voice put together from parts (ADR-062): the same parts always make the same
description, every description is one a learner could have written, and a description that
is no longer what its parts make is its own words."""

from __future__ import annotations

import itertools

import pytest

from adle_core.lessons.ir import is_plain_text
from adle_core.voice import design
from adle_core.voice.catalog import DEFAULT_DESIGN, MAX_DESIGN_CHARACTERS


def test_no_parts_at_all_is_adles_own_voice() -> None:
    assert design.compose({}) == DEFAULT_DESIGN
    assert design.compose(None) == DEFAULT_DESIGN
    # A part given as an empty choice is one left to the voice.
    assert design.compose({"speaker": "", "pace": ""}) == DEFAULT_DESIGN


def test_one_part_is_enough_for_a_whole_sentence() -> None:
    assert (
        design.compose({"speaker": "man"})
        == "A man with a clear voice, speaking natural English at an easy pace."
    )


def test_every_part_has_its_place_in_the_sentence() -> None:
    described = design.compose(
        {
            "speaker": "woman",
            "age": "older",
            "pitch": "low",
            "pace": "slow",
            "tone": "warm",
            "feeling": "enthusiastic",
            "steadiness": "steady",
            "accent": "british",
            "style": "storyteller",
        }
    )
    assert described == (
        "An enthusiastic elderly woman with a low-pitched, warm, mellow voice and a steady, "
        "even tone, speaking British English at a slow pace, like a storyteller reading aloud."
    )


def test_the_order_parts_are_given_in_does_not_change_the_voice() -> None:
    one = design.compose({"speaker": "man", "pace": "fast", "tone": "deep"})
    other = design.compose({"tone": "deep", "pace": "fast", "speaker": "man"})
    assert one == other


def test_a_part_or_a_choice_that_is_not_offered_is_refused() -> None:
    with pytest.raises(design.UnknownPartError):
        design.compose({"speaker": "robot"})
    with pytest.raises(design.UnknownPartError):
        design.compose({"species": "cat"})
    with pytest.raises(design.UnknownPartError):
        design.checked({"speaker": "man", "mood": "calm"})


def test_every_choice_is_named_once_and_says_something() -> None:
    assert len({part.key for part in design.PARTS}) == len(design.PARTS)
    for part in design.PARTS:
        keys = [option.key for option in part.options]
        names = [option.name for option in part.options]
        assert len(set(keys)) == len(keys), part.key
        assert len(set(names)) == len(names), part.key
        assert part.name
        for option in part.options:
            assert option.key
            assert option.name
            assert option.phrase
            assert option.key == option.key.lower()


def test_no_description_is_longer_than_one_a_learner_may_write() -> None:
    """Checked for every choice of the three parts that begin the sentence, with the longest
    choice of each part after them: a part's words add to the length whatever the others are."""
    start = [part for part in design.PARTS if part.key in ("feeling", "age", "speaker")]
    rest = {
        part.key: max(part.options, key=lambda option: len(option.phrase)).key
        for part in design.PARTS
        if part not in start
    }
    longest = 0
    for combination in itertools.product(*[["", *[o.key for o in part.options]] for part in start]):
        chosen = dict(rest)
        chosen.update({part.key: key for part, key in zip(start, combination, strict=True)})
        longest = max(longest, len(design.compose(chosen)))
    assert 150 < longest <= MAX_DESIGN_CHARACTERS


def test_every_description_is_plain_words_and_one_sentence() -> None:
    for part in design.PARTS:
        for option in part.options:
            described = design.compose({part.key: option.key})
            assert is_plain_text(described)
            assert described.endswith(".")
            assert described.count(".") == 1
            assert "  " not in described
            assert described[0] in "A"


def test_the_presets_are_choices_of_parts_that_are_offered() -> None:
    names = [preset.name for preset in design.PRESETS]
    assert len(set(names)) == len(names)
    assert design.PRESETS[0].parts == ()
    described = [design.compose(dict(preset.parts)) for preset in design.PRESETS]
    assert described[0] == DEFAULT_DESIGN
    # No two of them are the same voice.
    assert len(set(described)) == len(described)
    for preset in design.PRESETS[1:]:
        assert len(preset.parts) >= 3, preset.name


def test_a_description_remembers_its_parts_only_while_they_still_make_it() -> None:
    parts = {"speaker": "woman", "pace": "fast"}
    described = design.compose(parts)
    assert design.parts_of(parts, described) == parts
    # Written over by the learner since: its own words.
    assert design.parts_of(parts, described + " With a smile.") == {}
    # Kept by a version of Adle that offered something this one does not.
    assert design.parts_of({"speaker": "robot"}, described) == {}
    assert design.parts_of("woman", described) == {}
    assert design.parts_of(None, DEFAULT_DESIGN) == {}
    assert design.parts_of({}, DEFAULT_DESIGN) == {}
