"""How a lesson is formed (ADR-061): the rules of every lesson, what each subject needs
besides, the example each subject's writer is shown, and a course's subject from its name,
from the AI's plan, and from the learner. Against the scripted provider: no request leaves
the process.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient

from adle_core.api import schemas
from adle_core.application.generation import STRATEGY_ROTATION, next_strategy
from adle_core.application.services import Services
from adle_core.generation import prompts
from adle_core.generation.examples import EXAMPLES, written
from adle_core.generation.slides import _THEORY, compile_slide
from adle_core.infrastructure.orm import Course
from adle_core.lessons import axioms
from adle_core.lessons.ir import STRATEGIES, is_plain_text
from tests.support.model import CURRICULUM, FakeProvider
from tests.unit.test_course_setup import proposal, unnamed
from tests.unit.test_courses_and_sources import import_files
from tests.unit.test_generation_api import KEY, add_concept, finished


@pytest.fixture
def keyed(client: TestClient) -> TestClient:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    return client


def _one_line(text: str) -> str:
    return " ".join(text.split())


def lesson_prompt(provider: FakeProvider) -> str:
    """What the model was shown when it was last asked for a lesson's words (the requests
    after it are for that lesson's pictures)."""
    kinds = provider.kinds()
    return provider.prompt(len(kinds) - 1 - kinds[::-1].index("lesson"))


# -- the rules, written down once ------------------------------------------------------------------


def test_every_subject_says_how_its_lessons_go_to_the_learner_and_to_the_writer() -> None:
    assert axioms.SUBJECT_KEYS[-1] == axioms.GENERAL
    assert set(axioms.SUBJECT_KEYS) == set(get_args(schemas.SubjectKey))
    for subject in axioms.offered():
        assert subject.name[0].isupper()
        assert len(subject.steps) == 3
        assert all(0 < len(step) <= 60 for step in subject.steps)
        assert len(subject.brief) >= 3
        assert subject.strategies
        assert set(subject.strategies) <= set(STRATEGIES)
        assert subject.example in EXAMPLES
        assert axioms.subject_key(subject.name) == subject.key
        assert axioms.subject_key(subject.key) == subject.key
    # The general subject is taught every way there is, in the order it always was.
    assert axioms.ways_for(None) == STRATEGY_ROTATION
    assert axioms.ways_for("no such subject") == STRATEGY_ROTATION


def test_the_rules_of_every_lesson_are_short_for_the_learner_and_whole_for_the_writer() -> None:
    rules = axioms.rules_for_learner()
    assert len(rules) == len(axioms.AXIOMS) >= 5
    assert all(len(rule) <= 90 and rule.endswith(".") for rule in rules)
    assert len({axiom.key for axiom in axioms.AXIOMS}) == len(axioms.AXIOMS)
    # The case comes before the rule, and the rule before the name: in that order.
    keys = [axiom.key for axiom in axioms.AXIOMS]
    assert keys.index("case_first") < keys.index("rule_after") < keys.index("named_after_seen")


@pytest.mark.parametrize("key", axioms.SUBJECT_KEYS)
def test_a_writer_is_given_every_rule_and_its_own_subjects_needs(key: str) -> None:
    brief = _one_line(axioms.teaching_brief(key))
    for axiom in axioms.AXIOMS:
        assert _one_line(axiom.brief) in brief
    subject = axioms.subject(key)
    for line in subject.brief:
        assert _one_line(line) in brief
    for other in axioms.offered():
        if other.key != key:
            assert _one_line(other.brief[0]) not in brief
    assert max(len(line) for line in axioms.teaching_brief(key).split("\n")) <= 92


@pytest.mark.parametrize(
    ("name", "subject"),
    [
        ("Probability and counting", "mathematics"),
        ("Carbon and its Compounds", "chemistry"),
        ("Introduction to neural networks", "computer_science"),
        ("Week 3: Simple machines", "physics"),
        ("Newton's laws of motion", "physics"),
        ("The French Revolution", "history"),
        ("Passive voice", "language"),
        ("Spanish for beginners", "language"),
        ("English literature", "literature"),
        ("Shakespeare's sonnets", "literature"),
        ("The cell", "biology"),
        ("How do organisms reproduce", "biology"),
        ("Supply and demand", "economics"),
        ("Introduction to psychology", "social_science"),
        ("The water cycle", "earth_science"),
        ("Jazz harmony", "arts"),
        ("Rust and corrosion", "chemistry"),
        ("Large language models", "computer_science"),
        ("State of the art in deep learning", "computer_science"),
        # Nothing says, or two subjects say as much as each other: nobody is guessed for.
        ("New course", "general"),
        ("jesc104", "general"),
        ("Game theory", "general"),
        ("Physics of music", "general"),
        ("", "general"),
    ],
)
def test_a_courses_subject_is_guessed_from_its_name(name: str, subject: str) -> None:
    assert axioms.guess(name) == subject
    assert axioms.guess(None, name.upper(), None) == subject


def test_a_subject_is_known_by_the_names_a_model_may_give_it() -> None:
    known = {
        "Computer Science": "computer_science",
        "earth-science": "earth_science",
        "Maths": "mathematics",
        "languages": "language",
        "Social Sciences": "social_science",
        "Arts and music": "arts",
        "GENERAL": "general",
    }
    for said, key in known.items():
        assert axioms.subject_key(said) == key
    for nothing in ("", "alchemy", None, 3, ["history"]):
        assert axioms.subject_key(nothing) is None


def test_another_explanation_is_one_that_suits_the_subject() -> None:
    assert next_strategy([]) is None
    assert next_strategy(["visual"], "history") == "analogy"
    # History is not taught as mathematics, however many times it is asked for again.
    asked: list[str] = ["visual"]
    while (way := next_strategy(asked, "history")) is not None:
        asked.append(way)
    assert "mathematical" not in asked
    assert "computational" not in asked
    assert next_strategy(["visual", "worked_example"], "mathematics") == "mathematical"


# -- the example each subject is shown ----------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(EXAMPLES))
def test_an_example_obeys_the_rules_it_is_an_example_of(key: str) -> None:
    part = EXAMPLES[key].part
    visual = part["visual"]
    kinds = {element["id"]: element["kind"] for element in visual["elements"]}

    def shown(step: list[dict[str, Any]]) -> set[str]:
        named: set[str] = set()
        for action in step:
            for value in action.values():
                for ref in value if isinstance(value, list) else [value]:
                    if isinstance(ref, str):
                        named.add(ref.split(".")[0])
        return {name for name in named if name in kinds}

    # The case comes first and alone: no rule and no formula in the first step.
    assert {kinds[name] for name in shown(visual["steps"][0])}.isdisjoint(_THEORY)
    # And the rule comes last.
    assert {kinds[name] for name in shown(visual["steps"][-1])} & _THEORY
    # Each later step has its words in the narration, marked.
    said = " ".join(beat["say"] for beat in part["beats"])
    assert len(re.findall(r"\[[^\]]+\]", said)) == len(visual["steps"]) - 1
    # The narration opens on the case, and is words alone.
    assert all(
        is_plain_text(beat["say"].replace("[", "").replace("]", "")) for beat in part["beats"]
    )
    assert not re.search(r"[$\\]", said)
    # It is drawn whole: nothing of it left out, the case still first without any mending.
    slide = compile_slide(copy.deepcopy(visual))
    assert slide.left_out == []
    assert slide.steps == len(visual["steps"])


@pytest.mark.parametrize("key", sorted(EXAMPLES))
def test_an_example_is_shown_as_json_a_model_could_have_written(key: str) -> None:
    text = written(key)
    first, _, body = text.partition("\n")
    assert first.startswith("An example, for a part on ")
    assert first.endswith(":")
    assert json.loads(body) == EXAMPLES[key].part


def test_the_lesson_request_is_formed_for_its_subject() -> None:
    def request(subject: str | None) -> Any:
        return prompts.lesson_request(
            course_title="A course",
            concept=prompts.ConceptBrief("A concept", "", ["Name one."], []),
            learner=prompts.LearnerBrief("New to them.", "moderate", "moderate", ""),
            passages=[],
            subject=subject,
        )

    chemistry = request("chemistry")
    assert "expert teacher of chemistry" in chemistry.system
    assert "This course is chemistry." in chemistry.user
    assert "Baking soda meets vinegar" in chemistry.user
    assert "Area counts squares" not in chemistry.user
    # Every kind of picture can be asked for, whatever the subject.
    for kind in ('"timeline"', '"vessel"', '"molecule"', '"code"'):
        assert f"- {kind}:" in chemistry.user
    general = request(None)
    assert "expert teacher of the subject" in general.system
    assert "What each kind of subject needs besides:" in general.user
    assert "Area counts squares" in general.user
    assert request("no such subject").user == general.user
    # A lesson's request is no longer for one subject than for another by much.
    sizes = [len(request(key).user) for key in axioms.SUBJECT_KEYS]
    assert max(sizes) - min(sizes) < 2500


# -- a course's subject --------------------------------------------------------------------------------


def course(client: TestClient, course_id: str) -> dict[str, Any]:
    return dict(client.get(f"/v1/courses/{course_id}").json())


def test_a_course_is_placed_by_its_name_and_the_learner_can_place_it_themself(
    client: TestClient,
) -> None:
    made = client.post(
        "/v1/courses", json={"title": "Organic chemistry", "origin": "topic", "topic": "A start."}
    ).json()
    assert (made["subject"], made["subject_by_adle"]) == ("chemistry", True)

    chosen = client.patch(f"/v1/courses/{made['id']}", json={"subject": "biology"})
    assert chosen.status_code == 200, chosen.text
    assert (chosen.json()["subject"], chosen.json()["subject_by_adle"]) == ("biology", False)
    # Their choice stands, whatever the course is called afterwards.
    client.patch(f"/v1/courses/{made['id']}", json={"title": "The French Revolution"})
    assert course(client, made["id"])["subject"] == "biology"
    # "General" is a choice like any other, and stands too.
    client.patch(f"/v1/courses/{made['id']}", json={"subject": "general"})
    assert (
        course(client, made["id"])["subject"],
        course(client, made["id"])["subject_by_adle"],
    ) == (
        "general",
        False,
    )
    # Handed back, Adle places it by its name again.
    back = client.patch(f"/v1/courses/{made['id']}", json={"subject": "auto"}).json()
    assert (back["subject"], back["subject_by_adle"]) == ("history", True)

    refused = client.patch(f"/v1/courses/{made['id']}", json={"subject": "alchemy"})
    assert refused.status_code == 422
    assert course(client, made["id"])["subject"] == "history"


def test_a_course_named_from_its_first_file_is_placed_by_that_name(
    client: TestClient, services: Services
) -> None:
    made = unnamed(client)
    assert (made["subject"], made["subject_by_adle"]) == ("general", True)
    import_files(client, services, made["id"], "neural-networks-syllabus.md")
    after = course(client, made["id"])
    assert (after["title"], after["subject"]) == ("Neural networks syllabus", "computer_science")


def test_a_course_from_before_subjects_is_placed_as_the_core_starts(
    client: TestClient, services: Services
) -> None:
    made = client.post(
        "/v1/courses", json={"title": "Thermodynamics", "origin": "topic", "topic": "Heat."}
    ).json()
    kept = client.post(
        "/v1/courses", json={"title": "Poetry", "origin": "topic", "topic": "Sonnets."}
    ).json()
    client.patch(f"/v1/courses/{kept['id']}", json={"subject": "general"})
    with services.database.session() as session:
        # As revision 0014 leaves a course that was there before it.
        row = session.get(Course, made["id"])
        assert row is not None
        row.subject, row.subject_by_adle = "general", True
    services.courses.settle_subjects()
    assert course(client, made["id"])["subject"] == "physics"
    # One the learner placed is left where they put it.
    assert course(client, kept["id"])["subject"] == "general"


def test_the_ai_places_a_course_with_its_plan_unless_the_learner_has(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    made = unnamed(keyed, origin="topic", topic="Things worth knowing.")
    assert made["subject"] == "general"
    provider.queue({"subject": "Earth Science", **copy.deepcopy(CURRICULUM)})
    job = proposal(keyed, services, made["id"])
    assert '"subject" is one of "mathematics"' in provider.prompt()
    assert job["result"]["subject"] == "earth_science"
    after = course(keyed, made["id"])
    assert (after["subject"], after["subject_by_adle"]) == ("earth_science", True)

    # A subject that is none, or none at all, changes nothing.
    for nothing in ({"subject": "alchemy"}, {"subject": "general"}, {}):
        provider.queue({**nothing, **copy.deepcopy(CURRICULUM)})
        proposal(keyed, services, made["id"])
        assert course(keyed, made["id"])["subject"] == "earth_science"

    # The learner's choice is not undone by a plan.
    keyed.patch(f"/v1/courses/{made['id']}", json={"subject": "history"})
    provider.queue({"subject": "physics", **copy.deepcopy(CURRICULUM)})
    job = proposal(keyed, services, made["id"])
    assert job["result"]["subject"] == "history"
    assert course(keyed, made["id"])["subject"] == "history"


def test_a_lesson_is_asked_for_in_its_courses_subject(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    made = keyed.post(
        "/v1/courses", json={"title": "Acids, bases and salts", "origin": "topic", "topic": "pH."}
    ).json()
    concept = add_concept(keyed, made["id"], "Indicators")
    job = finished(services, keyed.post(f"/v1/concepts/{concept}/lessons"))
    assert job["status"] == "succeeded", job
    asked = lesson_prompt(provider)
    assert "expert teacher of chemistry" in asked
    assert "The case is an experiment" in _one_line(asked)
    assert "Baking soda meets vinegar" in asked

    # A course nobody has placed is formed by what its concept says.
    other = unnamed(keyed, origin="topic", topic="Things worth knowing.")
    added = keyed.post(
        f"/v1/courses/{other['id']}/concepts",
        json={
            "title": "The passive voice",
            "summary": "Sentences that begin with what is acted on.",
            "objectives": ["Rewrite an active sentence in the passive."],
        },
    )
    assert added.status_code in (200, 201), added.text
    sentence = added.json()["concepts"][0]["id"]
    finished(services, keyed.post(f"/v1/concepts/{sentence}/lessons"))
    assert "Everything is taught inside real sentences." in _one_line(lesson_prompt(provider))
    # And is not placed by that: the course itself says nothing yet.
    assert course(keyed, other["id"])["subject"] == "general"


def test_the_rules_are_told_to_the_learner_as_they_are_written(client: TestClient) -> None:
    told = client.get("/v1/lesson-rules")
    assert told.status_code == 200, told.text
    body = told.json()
    assert body["rules"] == axioms.rules_for_learner()
    assert [subject["key"] for subject in body["subjects"]] == list(axioms.SUBJECT_KEYS)
    chemistry = next(subject for subject in body["subjects"] if subject["key"] == "chemistry")
    assert chemistry == {
        "key": "chemistry",
        "name": "Chemistry",
        "steps": list(axioms.SUBJECTS["chemistry"].steps),
        "strategies": list(axioms.ways_for("chemistry")),
    }
