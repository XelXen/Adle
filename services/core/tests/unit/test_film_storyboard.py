"""A chapter's storyboard, looked over by a model that sees pictures (ADR-066).

The report is what the pinned engine (ManimGX 0.1.1) printed for the chapter the stand-in
provider writes (``fixtures/model-answers/film-chapter.py``), run as the film's second
chapter; the sheets are files the tests write where the engine writes its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adle_core.film import storyboard
from adle_core.film.report import read_report
from adle_core.film.storyboard import clear_sheets, seen, sheets, told
from tests.support.model import FILM_CHAPTER

DATA = Path(__file__).resolve().parents[1] / "data" / "film"
REPORT = read_report((DATA / "inspect-clean.txt").read_text(encoding="utf-8"))
CHAPTER = "chapter_02.py"
PNG = b"\x89PNG\r\n\x1a\n" + b"sheet"


def write_sheets(folder: Path, scene: str, count: int) -> list[bytes]:
    drawn = []
    for number in range(1, count + 1):
        name = f"{scene}.storyboard{'' if number == 1 else f'-{number}'}.png"
        data = PNG + bytes([number])
        (folder / name).write_bytes(data)
        drawn.append(data)
    return drawn


def test_the_sheets_are_read_in_the_order_of_their_numbers(tmp_path: Path) -> None:
    drawn = write_sheets(tmp_path, "Take", 11)
    write_sheets(tmp_path, "Film", 2)
    (tmp_path / "Take.storyboard.txt").write_text("not a sheet", encoding="utf-8")

    found = sheets(tmp_path, "Take")

    # In the order of their numbers (10 after 9, not after 1), at most eight, and only the
    # scene's own.
    assert found == drawn[: storyboard.MAX_SHEETS]


def test_the_sheets_stop_where_one_is_missing_or_is_not_a_picture(tmp_path: Path) -> None:
    drawn = write_sheets(tmp_path, "Take", 4)
    (tmp_path / "Take.storyboard-3.png").unlink()
    assert sheets(tmp_path, "Take") == drawn[:2]

    (tmp_path / "Take.storyboard-2.png").write_bytes(b"GIF89a")
    assert sheets(tmp_path, "Take") == drawn[:1]

    assert sheets(tmp_path / "nowhere", "Take") == []


def test_a_sheet_too_large_is_not_sent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    drawn = write_sheets(tmp_path, "Take", 2)
    (tmp_path / "Take.storyboard-2.png").write_bytes(PNG + b"x" * 64)
    monkeypatch.setattr(storyboard, "MAX_SHEET_BYTES", 32)
    assert sheets(tmp_path, "Take") == drawn[:1]


def test_a_folder_of_that_name_is_not_a_sheet(tmp_path: Path) -> None:
    drawn = write_sheets(tmp_path, "Take", 1)
    (tmp_path / "Take.storyboard-2.png").mkdir()
    assert sheets(tmp_path, "Take") == drawn


def test_what_an_earlier_run_drew_is_cleared_and_nothing_else(tmp_path: Path) -> None:
    write_sheets(tmp_path, "Take", 3)
    write_sheets(tmp_path, "Film", 1)
    (tmp_path / "take_02.py").write_text("", encoding="utf-8")

    clear_sheets(tmp_path, "Take")

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "Film.storyboard.png",
        "take_02.py",
    ]


def test_each_picture_is_told_with_what_is_said_while_it_plays() -> None:
    found = told(REPORT, FILM_CHAPTER, CHAPTER)

    assert [item.index for item in found] == list(range(17))
    assert found[0].said == "How much floor does a rug cover? Let us count it."
    assert (found[0].start, found[0].end) == (0.0, 4.69)
    # A line said over several lines of the file, its brackets gone.
    assert found[1].said == "Here is a rug, four squares wide and two squares tall."
    # An animation with no words: the circle drawn round the rule.
    assert found[7].said == ""
    # Another chapter's file says nothing of this one.
    assert all(item.said == "" for item in told(REPORT, FILM_CHAPTER, "chapter_03.py"))


def test_what_is_seen_is_told_by_the_line_that_played_it_and_when() -> None:
    answer = (
        "Looking at each picture in turn:\n"
        "#1: The label '2 tall' sits far to the left of the grid; put it beside the grid.\n"
        "- #7: The circle drawn round the rule is too thin to see.\n"
        "**#9:** The heading is crowded into the top left corner.\n"
        "Picture 12: The grid flashes in a color it never has elsewhere.\n"
        "1. #40: An arrow points at nothing.\n"
        "2. The whole thing is fine otherwise.\n"
    )

    assert seen(answer, REPORT, CHAPTER) == [
        "line 22, in the picture at 8.9 s: The label '2 tall' sits far to the left of the "
        "grid; put it beside the grid.",
        "line 47, in the picture at 32.8 s: The circle drawn round the rule is too thin to see.",
        "line 51, in the picture at 38.0 s: The heading is crowded into the top left corner.",
        "line 59, in the picture at 48.8 s: The grid flashes in a color it never has elsewhere.",
        # A picture that is not one of the chapter's: what is wrong is still told.
        "in one of the pictures: An arrow points at nothing.",
    ]


def test_nothing_seen_is_nothing_told() -> None:
    assert seen("NOTHING", REPORT, CHAPTER) == []
    assert seen("Nothing is wrong.\n", REPORT, CHAPTER) == []
    assert seen("", REPORT, CHAPTER) == []
    assert seen("#3: NOTHING", REPORT, CHAPTER) == []


def test_what_is_seen_is_bounded() -> None:
    answer = "\n".join(f"#{index % 17}: fault number {index} " + "x" * 400 for index in range(30))
    found = seen(answer, REPORT, CHAPTER)
    assert len(found) == storyboard.MAX_SEEN
    assert all(len(item) <= storyboard.MAX_SEEN_CHARACTERS for item in found)
    # The same fault said twice is told once.
    assert seen("#2: An arrow.\n#2: An arrow.", REPORT, CHAPTER) == [
        "line 30, in the picture at 13.3 s: An arrow."
    ]
