"""A question can have its part's picture drawn again, at the learner's word (ADR-067).

The picture is a slide the lesson's writer scripts and Adle draws, paced to the part's own
words, which never change. It is kept with the answer, joins the lesson only when the
learner uses it, and the part's own picture comes back when they put it back or remove the
note. No request in this file leaves the process.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from adle_core.application.generation import _marked_steps
from adle_core.application.services import Services
from adle_core.generation.drafts import DraftError, compile_redraw
from adle_core.generation.slides import slide_script
from adle_core.infrastructure.orm import StoredLesson
from tests.support.model import REDRAW, FakeProvider
from tests.unit.test_asks import KEY, a_lesson, finished, kept, part

WANT = "Draw the hydrogen bonds between the water molecules."


@pytest.fixture
def keyed(client: TestClient) -> TestClient:
    assert client.put("/v1/provider/credential", json={"api_key": KEY}).status_code == 204
    return client


def redraw(client: TestClient, lesson: Any, segment: Any, question: str = WANT) -> Any:
    return client.post(
        f"/v1/lessons/{lesson['lesson_id']}/asks",
        json={"segment_id": segment["id"], "question": question, "redraw": True},
    )


def played(client: TestClient, lesson: Any) -> Any:
    return client.get(f"/v1/lessons/{lesson['lesson_id']}").json()


def segment_of(found: Any, segment_id: str) -> Any:
    return next(item for item in found["lesson"]["segments"] if item["id"] == segment_id)


def test_a_part_s_picture_is_drawn_again_and_kept_with_the_answer_until_it_is_used(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    lesson = a_lesson(keyed, services)
    explained = part(lesson, "explanation")
    before = played(keyed, lesson)

    job = finished(services, redraw(keyed, lesson, explained))

    assert job.status == "succeeded", job.error_message
    assert provider.kinds()[-1] == "redraw"
    asked = provider.prompt()
    # The learner's words, quoted; the part's words with where its steps play; the slide's
    # vocabulary; and the request goes where a lesson would (the model that writes slides).
    assert '<learner_material kind="question">\n' + WANT in asked
    assert "A neuron receives several numbers" in asked
    assert '"elements"' in asked
    assert "It has no picture now." in asked
    (note,) = kept(keyed, lesson)
    assert note["picture"] == {
        "state": "offered",
        "description": REDRAW["visual"]["description"],
    }
    assert note["paragraphs"] == REDRAW["paragraphs"]
    # Nothing of it is in the lesson yet.
    assert played(keyed, lesson) == before


def test_a_picture_used_takes_the_part_s_place_its_words_stay_and_it_can_be_put_back(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    lesson = a_lesson(keyed, services)
    shown = part(lesson, "visualization")
    original = segment_of(played(keyed, lesson), shown["id"])
    finished(services, redraw(keyed, lesson, shown))
    (note,) = kept(keyed, lesson)

    used = keyed.post(f"/v1/lessons/{lesson['lesson_id']}/asks/{note['id']}/picture")

    assert used.status_code == 200, used.text
    now = segment_of(used.json(), shown["id"])
    assert now["scene"]["scene_id"].startswith("scn_ask_")
    assert now["scene"]["fallback_text"] == REDRAW["visual"]["description"]
    # The words are the part's own; only where its picture steps on has changed.
    assert [beat["text"] for beat in now["narration"]] == [
        beat["text"] for beat in original["narration"]
    ]
    scenes = {scene["id"]: scene for scene in used.json()["scenes"]}
    assert now["scene"]["scene_id"] in scenes
    assert original["scene"]["scene_id"] not in scenes
    # Its scene is a slide paced by those words, and keeps the script it was drawn from.
    drawn = scenes[now["scene"]["scene_id"]]
    assert drawn["steps"] == 2
    assert sum(len(beat["cues"]) for beat in now["narration"]) == 1
    assert slide_script(drawn["source"]) == {
        key: REDRAW["visual"][key] for key in ("elements", "steps", "description")
    }
    assert kept(keyed, lesson)[0]["picture"]["state"] == "in_use"
    # The lesson as it is read, every scene checked again, says the same.
    assert segment_of(played(keyed, lesson), shown["id"]) == now

    back = keyed.delete(f"/v1/lessons/{lesson['lesson_id']}/asks/{note['id']}/picture")

    assert back.status_code == 200, back.text
    assert segment_of(back.json(), shown["id"]) == original
    assert original["scene"]["scene_id"] in {scene["id"] for scene in back.json()["scenes"]}
    assert kept(keyed, lesson)[0]["picture"]["state"] == "offered"


def test_a_part_with_no_picture_is_given_one_and_a_picture_drawn_again_is_drawn_from_its_script(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    lesson = a_lesson(keyed, services)
    explained = part(lesson, "explanation")
    assert "scene" not in explained or explained["scene"] is None
    finished(services, redraw(keyed, lesson, explained))
    (first,) = kept(keyed, lesson)
    used = keyed.post(f"/v1/lessons/{lesson['lesson_id']}/asks/{first['id']}/picture")
    assert segment_of(used.json(), explained["id"])["scene"] is not None

    # Asked again, the writer is shown the slide it is now, to change what was asked.
    finished(services, redraw(keyed, lesson, explained, "Label the bond's two ends."))

    asked = provider.prompt()
    assert "Its picture now, as the slide it was drawn from:" in asked
    assert '"hydrogen bond"' in asked
    assert "Its picture takes 2 steps: the first as the part begins" in asked
    assert "⟨2⟩" in asked

    # Using the second takes the first out first: what is put back is the part's own.
    second = kept(keyed, lesson)[1]
    keyed.post(f"/v1/lessons/{lesson['lesson_id']}/asks/{second['id']}/picture")
    states = [note["picture"]["state"] for note in kept(keyed, lesson)]
    assert states == ["offered", "in_use"]
    back = keyed.delete(f"/v1/lessons/{lesson['lesson_id']}/asks/{second['id']}/picture")
    assert segment_of(back.json(), explained["id"]).get("scene") is None


def test_removing_a_note_whose_picture_is_in_use_gives_the_part_its_own_back(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    lesson = a_lesson(keyed, services)
    shown = part(lesson, "visualization")
    original = segment_of(played(keyed, lesson), shown["id"])
    finished(services, redraw(keyed, lesson, shown))
    (note,) = kept(keyed, lesson)
    keyed.post(f"/v1/lessons/{lesson['lesson_id']}/asks/{note['id']}/picture")

    removed = keyed.delete(f"/v1/lessons/{lesson['lesson_id']}/asks/{note['id']}")

    assert removed.status_code == 204
    assert segment_of(played(keyed, lesson), shown["id"]) == original
    assert kept(keyed, lesson) == []


def test_a_picture_that_cannot_be_drawn_is_asked_for_once_more_then_given_up(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    lesson = a_lesson(keyed, services)
    shown = part(lesson, "visualization")
    provider.queue(
        {"paragraphs": ["Here it is."], "visual": {"elements": [], "steps": []}},
        {"paragraphs": ["Here it is."]},
    )

    job = finished(services, redraw(keyed, lesson, shown))

    assert job.status == "failed"
    assert job.error_message.startswith("The picture couldn’t be drawn as asked, twice.")
    assert provider.kinds()[-2:] == ["redraw", "redraw"]
    # The second was told why the first could not be drawn.
    assert "The picture could not be drawn" in provider.prompt()
    assert kept(keyed, lesson) == []


def test_only_a_part_that_teaches_with_a_picture_can_have_it_drawn_again(
    keyed: TestClient, services: Services, provider: FakeProvider
) -> None:
    lesson = a_lesson(keyed, services)
    asked = len(provider.requests)
    refused = redraw(keyed, lesson, part(lesson, "checkpoint"))
    assert refused.status_code == 409
    assert refused.json()["error"]["message"] == "This part has no picture to change."
    # A part whose picture is still being drawn waits for it.
    shown = part(lesson, "visualization")
    with services.database.session() as session:
        row = session.scalars(
            select(StoredLesson).where(StoredLesson.id == lesson["lesson_id"])
        ).one()
        row.pending_scenes = [shown["scene"]["scene_id"]]
    waiting = redraw(keyed, lesson, shown)
    assert waiting.status_code == 409
    assert "still being drawn" in waiting.json()["error"]["message"]
    assert len(provider.requests) == asked


def test_a_redraw_is_paced_to_the_part_s_words_where_they_are() -> None:
    narration = [
        {"text": "Water molecules attract each other.", "cues": []},
        {"text": "A hydrogen on one is drawn to the oxygen of the next.", "cues": [2]},
    ]
    drawn = compile_redraw(json.dumps(REDRAW), narration)
    assert drawn.steps == 2
    assert drawn.cues == [[], [2]]
    assert drawn.paragraphs == REDRAW["paragraphs"]
    assert drawn.described == REDRAW["visual"]["description"]
    # A slide with a slider is something to try, not a picture to look at.
    slider = json.loads(json.dumps(REDRAW))
    slider["visual"]["elements"].append(
        {"id": "k", "kind": "param", "value": 1, "min": 0, "max": 2, "slider": True}
    )
    with pytest.raises(DraftError):
        compile_redraw(json.dumps(slider), narration)
    with pytest.raises(DraftError):
        compile_redraw('{"paragraphs": ["No picture."]}', narration)


def test_the_part_s_words_are_shown_with_where_each_step_plays() -> None:
    assert _marked_steps(
        [
            {"text": "First words. Then more.", "cues": [13]},
            {"text": "And the end.", "cues": [0, 4]},
        ]
    ) == ["First words. ⟨2⟩Then more.", "⟨3⟩And ⟨4⟩the end."]
