"""Courses, importing sources, and searching them, through the HTTP API."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adle_core.application.services import Services
from adle_core.application.sources import build_match_query, display_name_for

DOCUMENTS = Path(__file__).resolve().parents[4] / "fixtures" / "sample-documents"


def create_course(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body = {"title": "Neural networks", "origin": "materials", **overrides}
    response = client.post("/v1/courses", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def import_files(
    client: TestClient, services: Services, course_id: str, *names: str
) -> dict[str, Any]:
    """Start an import the way the desktop shell does, and wait for it to finish."""
    paths = [str(DOCUMENTS / name) for name in names]
    response = client.post(f"/v1/courses/{course_id}/sources/import", json={"paths": paths})
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] in {"queued", "running", "succeeded"}
    services.jobs.wait(job["id"])
    finished = client.get(f"/v1/jobs/{job['id']}").json()
    assert finished["status"] == "succeeded", finished
    return finished


def outcomes(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["file_name"]: entry for entry in job["result"]["files"]}


# -- courses ---------------------------------------------------------------


def test_course_lifecycle(client: TestClient) -> None:
    assert client.get("/v1/courses").json() == {"courses": []}

    course = create_course(client, description="  From my lecture notes  ")
    assert course["id"].startswith("crs_")
    assert course["description"] == "From my lecture notes"
    assert course["origin"] == "materials"
    assert course["source_count"] == 0
    assert course["concept_count"] == 0
    assert course["last_opened_at"] is None

    opened = client.get(f"/v1/courses/{course['id']}", params={"opened": True}).json()
    assert opened["last_opened_at"] is not None

    renamed = client.patch(f"/v1/courses/{course['id']}", json={"title": "Deep learning basics"})
    assert renamed.json()["title"] == "Deep learning basics"
    assert renamed.json()["description"] == "From my lecture notes"

    assert client.delete(f"/v1/courses/{course['id']}").status_code == 204
    assert client.get(f"/v1/courses/{course['id']}").status_code == 404
    assert client.get("/v1/courses").json() == {"courses": []}


def test_courses_are_listed_most_recently_used_first(client: TestClient) -> None:
    first = create_course(client, title="First")
    second = create_course(client, title="Second")
    third = create_course(client, title="Third")
    # The system clock on Windows ticks every ~16 ms; make "later" unambiguous.
    time.sleep(0.05)
    client.get(f"/v1/courses/{first['id']}", params={"opened": True})
    titles = [course["title"] for course in client.get("/v1/courses").json()["courses"]]
    assert titles[0] == "First"
    assert set(titles[1:]) == {second["title"], third["title"]}


def test_a_topic_course_needs_a_topic(client: TestClient) -> None:
    response = client.post("/v1/courses", json={"title": "Calculus", "origin": "topic"})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Describe the topic you want to learn."
    created = create_course(
        client, title="Calculus", origin="topic", topic="Limits and derivatives for beginners"
    )
    assert created["topic"] == "Limits and derivatives for beginners"


@pytest.mark.parametrize(
    "body",
    [
        {"title": "   ", "origin": "materials"},
        {"title": "x" * 201, "origin": "materials"},
        {"title": "T", "origin": "sample"},  # only Adle itself creates sample courses
        {"title": "T", "origin": "materials", "id": "crs_chosen_by_client"},
        {"title": "T", "origin": "materials", "description": "d" * 4001},
    ],
)
def test_invalid_course_input_is_rejected(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/v1/courses", json=body).status_code == 422
    assert client.get("/v1/courses").json() == {"courses": []}


def test_unknown_ids_are_not_found(client: TestClient) -> None:
    for method, path in [
        ("get", "/v1/courses/crs_missing"),
        ("patch", "/v1/courses/crs_missing"),
        ("delete", "/v1/courses/crs_missing"),
        ("get", "/v1/courses/crs_missing/sources"),
        ("get", "/v1/sources/src_missing"),
        ("delete", "/v1/sources/src_missing"),
        ("get", "/v1/jobs/job_missing"),
        ("post", "/v1/jobs/job_missing/cancel"),
    ]:
        kwargs = {"json": {}} if method == "patch" else {}
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 404, (method, path)
        assert response.json()["error"]["code"] == "not_found"
    assert client.get("/v1/courses/crs_missing/search", params={"q": "x"}).status_code == 404


# -- importing -------------------------------------------------------------


def test_importing_every_supported_format_keeps_provenance(
    client: TestClient, services: Services
) -> None:
    course = create_course(client)
    job = import_files(
        client,
        services,
        course["id"],
        "neural-networks-syllabus.md",
        "lecture-notes.pdf",
        "course-outline.docx",
        "study-notes.txt",
    )
    assert (job["progress_done"], job["progress_total"]) == (4, 4)
    assert {entry["outcome"] for entry in job["result"]["files"]} == {"imported"}

    sources = client.get(f"/v1/courses/{course['id']}/sources").json()["sources"]
    by_name = {source["display_name"]: source for source in sources}
    assert set(by_name) == {
        "neural-networks-syllabus.md",
        "lecture-notes.pdf",
        "course-outline.docx",
        "study-notes.txt",
    }
    assert by_name["lecture-notes.pdf"]["kind"] == "pdf"
    assert by_name["lecture-notes.pdf"]["page_count"] == 3
    assert by_name["neural-networks-syllabus.md"]["page_count"] == 0
    assert by_name["neural-networks-syllabus.md"]["section_count"] > 10
    assert all(source["status"] == "extracted" for source in sources)
    assert all(source["chunk_count"] >= 1 and source["char_count"] > 0 for source in sources)
    assert client.get(f"/v1/courses/{course['id']}").json()["source_count"] == 4

    detail = client.get(f"/v1/sources/{by_name['lecture-notes.pdf']['id']}").json()
    assert [section["page_number"] for section in detail["sections"]] == [1, 2, 3]
    assert all(section["kind"] == "page" for section in detail["sections"])


def test_original_files_are_copied_under_generated_names(
    client: TestClient, services: Services
) -> None:
    course = create_course(client)
    import_files(client, services, course["id"], "study-notes.txt")
    source = client.get(f"/v1/courses/{course['id']}/sources").json()["sources"][0]
    stored = list(services.settings.sources_dir.iterdir())
    assert [path.name for path in stored] == [f"{source['id']}.txt"]
    assert stored[0].read_bytes() == (DOCUMENTS / "study-notes.txt").read_bytes()
    # The learner's original path is not kept anywhere in the API.
    assert str(DOCUMENTS) not in client.get(f"/v1/sources/{source['id']}").text


def test_importing_the_same_file_twice_does_not_duplicate_it(
    client: TestClient, services: Services, tmp_path: Path
) -> None:
    course = create_course(client)
    import_files(client, services, course["id"], "study-notes.txt")

    # Same bytes under a different name are still the same source.
    renamed = tmp_path / "renamed-copy.txt"
    shutil.copyfile(DOCUMENTS / "study-notes.txt", renamed)
    response = client.post(
        f"/v1/courses/{course['id']}/sources/import", json={"paths": [str(renamed)]}
    )
    job = services.jobs.wait(response.json()["id"])
    entry = job.result["files"][0]
    assert entry["outcome"] == "duplicate"
    assert entry["message"] == "This file is already in the course."

    assert len(client.get(f"/v1/courses/{course['id']}/sources").json()["sources"]) == 1
    assert len(list(services.settings.sources_dir.iterdir())) == 1

    # The same file may belong to a different course.
    other = create_course(client, title="Another course")
    again = import_files(client, services, other["id"], "study-notes.txt")
    assert again["result"]["files"][0]["outcome"] == "imported"


def test_a_bad_file_does_not_stop_the_rest_of_the_import(
    client: TestClient, services: Services
) -> None:
    course = create_course(client)
    job = import_files(
        client,
        services,
        course["id"],
        "scanned-handout.pdf",
        "study-notes.txt",
        "lecture-notes-encrypted.pdf",
        "damaged.pdf",
        "partly-scanned.pdf",
        "does-not-exist.pdf",
    )
    result = outcomes(job)
    assert result["study-notes.txt"]["outcome"] == "imported"
    assert result["partly-scanned.pdf"]["outcome"] == "imported"
    assert "no selectable text" in result["partly-scanned.pdf"]["warnings"][0]
    assert result["scanned-handout.pdf"]["error_code"] == "scanned_document"
    assert result["lecture-notes-encrypted.pdf"]["error_code"] == "encrypted_document"
    assert result["damaged.pdf"]["error_code"] == "malformed_document"
    assert result["does-not-exist.pdf"]["error_code"] == "file_unreadable"
    for name in ("scanned-handout.pdf", "damaged.pdf"):
        assert result[name]["outcome"] == "rejected"
        assert result[name]["message"]

    sources = client.get(f"/v1/courses/{course['id']}/sources").json()["sources"]
    statuses = {source["display_name"]: source["status"] for source in sources}
    assert statuses == {"study-notes.txt": "extracted", "partly-scanned.pdf": "needs_attention"}
    # Nothing from a rejected file is left behind on disk.
    assert len(list(services.settings.sources_dir.iterdir())) == 2


def test_import_requests_are_validated(client: TestClient) -> None:
    course = create_course(client)
    url = f"/v1/courses/{course['id']}/sources/import"
    assert client.post(url, json={"paths": []}).status_code == 422
    assert client.post(url, json={"paths": ["relative/notes.txt"]}).status_code == 422
    too_many = [str(DOCUMENTS / "study-notes.txt")] * 51
    assert client.post(url, json={"paths": too_many}).status_code == 422
    missing_course = client.post(
        "/v1/courses/crs_missing/sources/import",
        json={"paths": [str(DOCUMENTS / "study-notes.txt")]},
    )
    assert missing_course.status_code == 404


def test_deleting_a_source_removes_its_file_and_its_passages(
    client: TestClient, services: Services
) -> None:
    course = create_course(client)
    import_files(client, services, course["id"], "study-notes.txt", "lecture-notes.pdf")
    sources = client.get(f"/v1/courses/{course['id']}/sources").json()["sources"]
    notes = next(source for source in sources if source["kind"] == "text")

    assert client.delete(f"/v1/sources/{notes['id']}").status_code == 204
    remaining = client.get(f"/v1/courses/{course['id']}/sources").json()["sources"]
    assert [source["kind"] for source in remaining] == ["pdf"]
    assert [path.suffix for path in services.settings.sources_dir.iterdir()] == [".pdf"]
    search = client.get(f"/v1/courses/{course['id']}/search", params={"q": "ball rolling"})
    assert search.json()["hits"] == []


def test_deleting_a_course_removes_everything_it_owned(
    client: TestClient, services: Services
) -> None:
    keep = create_course(client, title="Keep")
    remove = create_course(client, title="Remove")
    import_files(client, services, keep["id"], "study-notes.txt")
    import_files(client, services, remove["id"], "study-notes.txt", "lecture-notes.pdf")
    assert len(list(services.settings.sources_dir.iterdir())) == 3

    assert client.delete(f"/v1/courses/{remove['id']}").status_code == 204
    assert len(list(services.settings.sources_dir.iterdir())) == 1
    kept = client.get(f"/v1/courses/{keep['id']}/search", params={"q": "learning rate"}).json()
    assert len(kept["hits"]) >= 1


# -- searching -------------------------------------------------------------


def test_search_returns_passages_with_their_source_and_location(
    client: TestClient, services: Services
) -> None:
    course = create_course(client)
    import_files(client, services, course["id"], "neural-networks-syllabus.md", "lecture-notes.pdf")

    pdf_hits = client.get(
        f"/v1/courses/{course['id']}/search", params={"q": "worked example updated weight"}
    ).json()["hits"]
    assert pdf_hits[0]["source_name"] == "lecture-notes.pdf"
    assert pdf_hits[0]["page_number"] == 3
    assert pdf_hits[0]["section_title"] is None

    md_hits = client.get(f"/v1/courses/{course['id']}/search", params={"q": "bias shifts"}).json()[
        "hits"
    ]
    assert md_hits[0]["source_name"] == "neural-networks-syllabus.md"
    assert md_hits[0]["section_title"].endswith("Weights and bias")
    assert md_hits[0]["page_number"] is None

    highlighted = [seg["text"].lower() for seg in md_hits[0]["excerpt"] if seg["highlighted"]]
    assert "bias" in highlighted
    # The excerpt is plain text split into segments: no markup, no marker characters.
    joined = "".join(segment["text"] for segment in md_hits[0]["excerpt"])
    assert "<" not in joined
    assert chr(0xE000) not in joined
    assert chr(0xE001) not in joined


def test_search_is_scoped_to_one_course(client: TestClient, services: Services) -> None:
    first = create_course(client, title="First")
    second = create_course(client, title="Second")
    import_files(client, services, first["id"], "study-notes.txt")
    assert client.get(f"/v1/courses/{second['id']}/search", params={"q": "gradient"}).json() == {
        "query": "gradient",
        "hits": [],
    }
    assert client.get(f"/v1/courses/{first['id']}/search", params={"q": "gradient"}).json()["hits"]


def test_passages_for_a_lesson_are_found_by_a_word_in_any_of_its_forms(
    client: TestClient, services: Services
) -> None:
    course = create_course(client)
    import_files(client, services, course["id"], "study-notes.txt")
    # The notes say "weight" and "weights", never "weighted": a concept may say it that way.
    found = services.retriever.retrieve(course["id"], "weighted")
    assert found
    assert any("weight" in passage.text.lower() for passage in found)
    # Searching while typing keeps matching the start of a word, from the index it had.
    assert client.get(f"/v1/courses/{course['id']}/search", params={"q": "learni"}).json()["hits"]


def test_search_falls_back_to_any_term_and_matches_prefixes(
    client: TestClient, services: Services
) -> None:
    course = create_course(client)
    import_files(client, services, course["id"], "study-notes.txt")
    search = lambda q: client.get(  # noqa: E731
        f"/v1/courses/{course['id']}/search", params={"q": q}
    ).json()["hits"]
    assert search("gradient zebra")  # "zebra" is nowhere; "gradient" still finds the notes
    assert search("grad")  # prefix of the last word, as when typing
    assert search("xylophone") == []


@pytest.mark.parametrize(
    "query",
    [
        '"unbalanced',
        "NEAR(a b)",
        "a AND",
        "col:umn",
        "* * *",
        "(((",
        "a OR OR b",
        "-minus",
        "^caret",
    ],
)
def test_search_input_is_never_interpreted_as_query_syntax(
    client: TestClient, services: Services, query: str
) -> None:
    course = create_course(client)
    import_files(client, services, course["id"], "study-notes.txt")
    response = client.get(f"/v1/courses/{course['id']}/search", params={"q": query})
    assert response.status_code == 200
    assert isinstance(response.json()["hits"], list)


def test_search_query_limits(client: TestClient) -> None:
    course = create_course(client)
    url = f"/v1/courses/{course['id']}/search"
    assert client.get(url, params={"q": ""}).status_code == 422
    assert client.get(url, params={"q": "x" * 201}).status_code == 422
    assert client.get(url, params={"q": "x", "limit": 0}).status_code == 422
    assert client.get(url, params={"q": "x", "limit": 21}).status_code == 422


def test_match_query_builder() -> None:
    assert build_match_query("chain rule", require_all=True) == '"chain" AND "rule"*'
    assert build_match_query("chain rule", require_all=False) == '"chain" OR "rule"*'
    assert build_match_query('  "; DROP TABLE  ', require_all=True) == '"DROP" AND "TABLE"*'
    assert build_match_query("!!! ???", require_all=True) is None
    assert build_match_query(" ".join(["w"] * 40), require_all=True).count('"w"') == 12


def test_display_names_are_safe_labels() -> None:
    assert display_name_for(Path("/home/user/My Notes.pdf")) == "My Notes.pdf"
    assert display_name_for(Path("bad" + chr(7) + chr(0x202E) + "name.txt")) == "badname.txt"
    assert len(display_name_for(Path("x" * 400 + ".txt"))) == 255


def test_the_import_route_is_internal(services: Services) -> None:
    """Only the desktop shell may name file paths; the renderer allowlist excludes this route."""
    from adle_core.api.app import create_app

    paths = create_app(services).openapi()["paths"]
    assert paths["/v1/courses/{course_id}/sources/import"]["post"]["x-adle-internal"] is True
    for path, methods in paths.items():
        for method, operation in methods.items():
            if "paths" in str(operation.get("requestBody", "")) or path.endswith("/import"):
                assert operation.get("x-adle-internal") is True, (method, path)


def test_a_file_far_past_the_limit_is_refused_before_any_of_it_is_read(
    client: TestClient, services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whether a file is here already is found by reading all of it: not worth gigabytes."""
    import dataclasses

    from adle_core.application import sources as sources_module

    read: list[Path] = []
    hash_file = sources_module.hash_file

    def recorded(path: Path) -> tuple[str, int]:
        read.append(path)
        return hash_file(path)

    monkeypatch.setattr(sources_module, "hash_file", recorded)
    monkeypatch.setattr(
        services.sources,
        "_limits",
        dataclasses.replace(services.sources._limits, max_file_bytes=1000),
    )
    course = create_course(client)
    job = import_files(client, services, course["id"], "lecture-notes.pdf", "study-notes.txt")
    result = outcomes(job)

    assert result["lecture-notes.pdf"]["outcome"] == "rejected"
    assert result["lecture-notes.pdf"]["error_code"] == "file_too_large"
    assert "Split it into smaller parts" in result["lecture-notes.pdf"]["message"]
    # The small file beside it was read and imported; the large one was never opened.
    assert result["study-notes.txt"]["outcome"] == "imported"
    assert [path.name for path in read] == ["study-notes.txt"]
