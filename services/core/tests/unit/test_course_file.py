"""A course file read as one that may come from anywhere (ADR-063): nothing is extracted, a
member is read only by a name Adle made and never past a bound, and every part is checked
against a closed description of it."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from adle_core.application import course_file as files
from adle_core.application.course_file import CourseFileError, CourseFileNewerError

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
CONCEPT = "con_" + "1" * 20
OTHER = "con_" + "2" * 20
SOURCE = "src_" + "3" * 20
SECTION = "sec_" + "4" * 20


def manifest(**changes: Any) -> dict[str, Any]:
    made = {
        "format": "adle-course",
        "version": 1,
        "kind": "template",
        "made_by": "Adle 0.1.0",
        "made_at": NOW.isoformat(),
        "course": {"title": "Limits", "subject": "mathematics"},
        "counts": {
            "concepts": 1,
            "lessons": 0,
            "materials": 0,
            "files": 0,
            "progress": False,
            "notes": 0,
        },
    }
    made.update(changes)
    return made


def curriculum() -> dict[str, Any]:
    return {
        "concepts": [
            {
                "id": CONCEPT,
                "title": "A limit",
                "objectives": [{"id": "obj_" + "5" * 20, "statement": "Estimate a limit."}],
                "needs": [{"concept_id": OTHER, "reason": "It is built on it."}],
            }
        ]
    }


def material() -> dict[str, Any]:
    return {
        "id": SOURCE,
        "display_name": "Notes.md",
        "kind": "markdown",
        "content_hash": "a" * 64,
        "size_bytes": 5,
        "parser": "markdown",
        "parser_version": "1",
        "sections": [{"id": SECTION, "kind": "heading", "title": "Limits", "level": 1}],
        "chunks": [
            {
                "section": 0,
                "text": "A limit is what a function approaches.",
                "char_start": 0,
                "char_end": 38,
                "content_hash": "b" * 64,
            }
        ],
    }


def a_file(path: Path, members: dict[str, Any]) -> Path:
    """A zip of these members: a mapping is written as JSON, bytes as they are."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in members.items():
            archive.writestr(name, value if isinstance(value, bytes) else json.dumps(value))
    return path


def whole(**more: Any) -> dict[str, Any]:
    return {"adle-course.json": manifest(), "curriculum.json": curriculum(), **more}


def test_what_is_written_is_what_is_read(tmp_path: Path) -> None:
    original = tmp_path / "notes.md"
    original.write_bytes(b"hello")
    made = files.Manifest.model_validate(manifest(kind="transfer"))
    plan = files.Curriculum.model_validate(curriculum())
    lesson = files.LessonPart(lesson={"lesson_id": "les_" + "6" * 20, "title": "A limit"})
    source = files.SourcePart.model_validate(material())
    progress = files.Progress(
        observations=[
            files.ObservationPart(
                concept_id=CONCEPT, occurred_at=NOW, kind="answer", outcome="correct"
            )
        ]
    )
    notes = files.Notes()
    path = tmp_path / "course.zip"
    files.write_course_file(
        path,
        manifest=made,
        curriculum=plan,
        lessons=[lesson],
        materials=[(source, original)],
        progress=progress,
        notes=notes,
    )
    assert files.read_manifest(path) == made
    read = files.read_course_file(path)
    assert (read.manifest, read.curriculum) == (made, plan)
    assert read.lessons == (lesson,)
    assert read.materials == (source,)
    assert read.originals == {0: "materials/0001.file"}
    assert (read.progress, read.notes) == (progress, notes)
    kept = io.BytesIO()
    files.copy_original(path, read.originals[0], kept, limit=1_000)
    assert kept.getvalue() == b"hello"
    # A file's members are the ones this module makes, and no others.
    with zipfile.ZipFile(path) as archive:
        assert sorted(archive.namelist()) == [
            "adle-course.json",
            "curriculum.json",
            "lessons/0001.json",
            "materials/0001.file",
            "materials/0001.json",
            "notes.json",
            "progress.json",
        ]


def test_a_template_has_nothing_of_the_learner_in_it(tmp_path: Path) -> None:
    path = a_file(tmp_path / "course.zip", whole())
    read = files.read_course_file(path)
    assert (read.progress, read.notes, read.materials, read.lessons) == (None, None, (), ())


@pytest.mark.parametrize(
    "members",
    [
        {},
        {"curriculum.json": curriculum()},
        {"adle-course.json": manifest()},
        {"adle-course.json": manifest(format="something-else"), "curriculum.json": curriculum()},
        {"adle-course.json": manifest(version=0), "curriculum.json": curriculum()},
        {"adle-course.json": manifest(kind="everything"), "curriculum.json": curriculum()},
        {"adle-course.json": manifest(extra="field"), "curriculum.json": curriculum()},
        {"adle-course.json": b"not json", "curriculum.json": curriculum()},
        {"adle-course.json": [1, 2, 3], "curriculum.json": curriculum()},
        {"adle-course.json": manifest(), "curriculum.json": {"concepts": [{"id": "x"}]}},
        {"adle-course.json": manifest(), "curriculum.json": b"\xff\xfe"},
    ],
)
def test_a_file_that_is_not_a_course_is_refused(tmp_path: Path, members: dict[str, Any]) -> None:
    path = a_file(tmp_path / "course.zip", members)
    with pytest.raises(CourseFileError):
        files.read_course_file(path)


def test_something_that_is_not_a_zip_at_all_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "course.zip"
    path.write_bytes(b"MZ\x90\x00 not a zip at all")
    with pytest.raises(CourseFileError):
        files.read_manifest(path)
    with pytest.raises(CourseFileError):
        files.read_course_file(tmp_path / "missing.zip")


def test_a_file_from_a_newer_adle_says_so(tmp_path: Path) -> None:
    path = a_file(tmp_path / "course.zip", whole(**{"adle-course.json": manifest(version=2)}))
    with pytest.raises(CourseFileNewerError) as refused:
        files.read_manifest(path)
    assert refused.value.code == "course_file_newer"
    assert "newer version" in refused.value.message


@pytest.mark.parametrize(
    "name",
    [
        "../outside.json",
        "..\\outside.json",
        "/etc/passwd",
        "C:/Windows/system.ini",
        "lessons/../../x.json",
        "lessons/1.json",
        "lessons/0001.txt",
        "materials/0001.exe",
        "materials/0001.file/extra",
        "readme.txt",
        "adle-course.json/",
        "lessons/0001.json\x00.png",
    ],
)
def test_a_member_adle_did_not_make_refuses_the_whole_file(tmp_path: Path, name: str) -> None:
    """Nothing is ever extracted, so a name could go nowhere: it is refused all the same,
    because a file with something else in it is not one Adle made."""
    path = a_file(tmp_path / "course.zip", whole(**{name: {"x": 1}}))
    with pytest.raises(CourseFileError):
        files.read_course_file(path)
    assert list(tmp_path.iterdir()) == [path]


def test_lessons_and_materials_are_numbered_from_one_with_no_gaps(tmp_path: Path) -> None:
    lesson = {"lesson": {"title": "x"}}
    for members in (
        whole(**{"lessons/0002.json": lesson}),
        whole(**{"lessons/0001.json": lesson, "lessons/0003.json": lesson}),
        whole(**{"materials/0001.file": b"an original with no material"}),
        whole(**{"lessons/0000.json": lesson}),
    ):
        path = a_file(tmp_path / "course.zip", members)
        with pytest.raises(CourseFileError):
            files.read_course_file(path)


def test_a_member_is_never_read_past_its_bound_whatever_the_file_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A small file can unpack to a great deal. What a part may be is bounded as it is read,
    not by the size the file gives for it."""
    monkeypatch.setattr(files, "MAX_CURRICULUM_BYTES", 2_000)
    big = {"concepts": [], "padding": "x" * 50_000}
    path = a_file(tmp_path / "course.zip", {"adle-course.json": manifest(), "curriculum.json": big})
    assert path.stat().st_size < 2_000
    with pytest.raises(CourseFileError):
        files.read_course_file(path)

    # The same for the whole of a file, across its members.
    monkeypatch.setattr(files, "MAX_CURRICULUM_BYTES", 8 * 1024 * 1024)
    monkeypatch.setattr(files, "MAX_TOTAL_BYTES", 10_000)
    lesson = {"lesson": {"title": "x" * 6_000}}
    path = a_file(
        tmp_path / "course.zip",
        whole(**{"lessons/0001.json": lesson, "lessons/0002.json": lesson}),
    )
    with pytest.raises(CourseFileError):
        files.read_course_file(path)


def test_a_size_the_file_lies_about_is_caught_as_it_is_read(tmp_path: Path) -> None:
    path = a_file(tmp_path / "course.zip", whole())
    original = tmp_path / "big.bin"
    original.write_bytes(b"0" * 4_000)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("materials/0001.json", json.dumps(material()))
        archive.write(original, "materials/0001.file")
    read = files.read_course_file(path)
    with pytest.raises(CourseFileError):
        files.copy_original(path, read.originals[0], io.BytesIO(), limit=1_000)
    # And only a document is ever copied out: not a member of another kind.
    with pytest.raises(CourseFileError):
        files.copy_original(path, "adle-course.json", io.BytesIO(), limit=1_000_000)


def test_a_file_with_two_members_of_one_name_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "course.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("adle-course.json", json.dumps(manifest()))
        archive.writestr("curriculum.json", json.dumps(curriculum()))
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("curriculum.json", json.dumps({"concepts": []}))
    with pytest.raises(CourseFileError):
        files.read_course_file(path)


def test_too_many_members_are_not_looked_through(tmp_path: Path) -> None:
    path = tmp_path / "course.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("adle-course.json", json.dumps(manifest()))
        archive.writestr("curriculum.json", json.dumps(curriculum()))
        for index in range(2 * (files.MAX_LESSONS + files.MAX_MATERIALS) + 9):
            archive.writestr(f"lessons/{index + 1:04d}.json", "{}")
    with pytest.raises(CourseFileError):
        files.read_course_file(path)


@pytest.mark.parametrize(
    ("part", "broken"),
    [
        ("curriculum.json", {"concepts": [{"id": CONCEPT, "title": ""}]}),
        ("curriculum.json", {"concepts": [{"id": "../../x", "title": "A limit"}]}),
        ("curriculum.json", {"concepts": [{"id": CONCEPT, "title": "x", "complexity": 9}]}),
        ("curriculum.json", {"concepts": [{"id": CONCEPT, "title": "x", "origin": "adle"}]}),
        ("progress.json", {"observations": [{"concept_id": CONCEPT, "kind": "answer"}]}),
        (
            "progress.json",
            {
                "observations": [
                    {
                        "concept_id": CONCEPT,
                        "occurred_at": NOW.isoformat(),
                        "kind": "answer",
                        "outcome": "perfect",
                    }
                ]
            },
        ),
        ("progress.json", {"probability": 0.99}),
        ("notes.json", {"asks": [{"lesson_id": "x"}]}),
        ("materials/0001.json", {**material(), "kind": "executable"}),
        ("materials/0001.json", {**material(), "stored_name": "../../evil"}),
        ("lessons/0001.json", {"lesson": "not a lesson"}),
        ("lessons/0001.json", {"lesson": {}, "origin": "sample"}),
    ],
)
def test_a_part_that_is_not_what_it_should_be_refuses_the_file(
    tmp_path: Path, part: str, broken: dict[str, Any]
) -> None:
    path = a_file(tmp_path / "course.zip", whole(**{part: broken}))
    with pytest.raises(CourseFileError):
        files.read_course_file(path)


def test_what_a_file_says_a_learner_knows_has_nowhere_to_go() -> None:
    """A file carries what the learner did, never what it adds up to: there is no field for
    a state, a probability or a sentence about either."""
    fields = set(files.ObservationPart.model_fields)
    assert not fields & {"state_before", "state_after", "explanation", "probability", "state"}
    assert "probability" not in files.Progress.model_fields
