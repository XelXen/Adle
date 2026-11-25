"""What the film engine says of a scene, read into what a chapter's writer is told (ADR-065).

The reports here are what the pinned engine (ManimGX 0.1.1) printed, on 2026-11-24, for
chapters written to go wrong in each way: words over words, a table past the edges, a sign
too small to read (which is no fault), and a formula the typesetter stopped on.
"""

from __future__ import annotations

from pathlib import Path

from adle_core.film.report import chapter_starts, findings, read_report

DATA = Path(__file__).resolve().parents[1] / "data" / "film"


def reported(name: str) -> str:
    return (DATA / name).read_text(encoding="utf-8")


def test_a_clean_chapter_has_its_length_and_its_plays_by_line() -> None:
    report = read_report(reported("inspect-clean.txt"))
    assert report.ran
    assert report.clean
    assert report.seconds == 62.13
    assert len(report.plays) == 17
    first = report.plays[0]
    assert (first.index, first.start, first.end, first.file, first.line) == (
        0,
        0.0,
        4.69,
        "chapter_02.py",
        14,
    )
    assert first.what.startswith("say 'How much floor")
    assert findings(report, "chapter_02.py") == []


def test_what_lies_wrong_is_found_by_the_line_of_the_chapter() -> None:
    report = read_report(reported("inspect-layout.txt"))
    assert report.ran
    assert not report.clean
    # Three were reported; a sign too small to read is short by nature and not a fault.
    assert [problem.line for problem in report.problems] == [9, 14]
    told = findings(report, "chapter_02.py")
    assert told[0].startswith("line 9, at 4.5 s: title (Text 'Words over words') and over")
    assert "texts overlap" in told[0]
    assert told[1] == (
        "line 14, at 7.5 s: table (Table): 3.30 past the left edge, 7.30 past the right edge"
    )


def test_a_scene_that_stopped_says_where_and_why() -> None:
    report = read_report("", reported("inspect-stopped.txt"))
    assert not report.ran
    assert report.failure is not None
    assert (report.failure.file, report.failure.line) == ("chapter_03.py", 6)
    assert report.failure.text == r"TypstError: error: unknown command: \fr"
    assert findings(report, "chapter_03.py") == [
        r"line 6: the scene stopped here. TypstError: error: unknown command: \fr"
    ]
    # A line of a file around the chapter is not one its writer can mend by number.
    assert findings(report, "chapter_02.py")[0].startswith("the scene stopped here.")


def test_a_made_video_says_how_long_it_is_and_its_notes_are_not_faults() -> None:
    report = read_report(reported("render.txt"))
    assert report.seconds == 10.56
    assert report.ran
    assert report.problems == ()


def test_what_is_told_is_bounded() -> None:
    lines = [
        f"  [{index}] t=1.0s (chapter_02.py:{index})  label (Text '{'x' * 400}'): texts overlap"
        for index in range(1, 40)
    ]
    report = read_report(
        "take_02.py: Take, 5.00 s, 1 play\nlayout: 39 problems\n" + "\n".join(lines)
    )
    told = findings(report, "chapter_02.py")
    assert len(told) == 14
    assert all(len(item) <= 300 for item in told)


def test_a_film_says_when_each_chapter_begins() -> None:
    out = "\n".join(
        [
            "film.py: Film, 30.00 s, 4 plays",
            "  #0   0.00– 5.00s  chapter_01.py:7  say 'This film goes through…'",
            "  #1   5.00– 6.00s  film.py:30  FadeOut(Group)",
            "  #2   6.40–20.00s  chapter_02.py:14  say 'How much floor…'",
            "  #3  20.00–30.00s  chapter_02.py:20  say 'Count the squares…'",
        ]
    )
    report = read_report(out)
    assert chapter_starts(report, ["chapter_01.py", "chapter_02.py", "chapter_03.py"]) == {
        "chapter_01.py": 0.0,
        "chapter_02.py": 6.4,
    }
