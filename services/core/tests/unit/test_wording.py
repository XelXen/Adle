"""What a learner reads is in American English (ADR-044).

Every sentence the core can say (its strings, read by Python's own parser, so that comments
and docstrings do not count), every text of the sample course, and the pictures' labels. The
API's own names are identifiers, not words a learner reads, and keep the spelling they have;
so do the database's, in its schema and its migrations.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import adle_core

CORE = Path(adle_core.__file__).parent
BRITISH = re.compile(
    r"\b(?:colour|behaviour|organis|recognis|favourit|centre|learnt|analys(?:e|ed|ing)\b|"
    r"summaris|realis|maths\b|cancell|labell|modell|grey|programme|judgement|licence|practis|"
    r"towards|whilst|amongst|catalogue|neighbour|honour|favour|minimis|maximis|normalis|"
    r"visualis|optimis|initialis)\w*",
    re.IGNORECASE,
)
#: Names the API gives things: a job that was stopped, a step that is practice. And a name
#: a model may write in a scene ("colour=" for "color="), which the scene policy must know
#: by that spelling to refuse it, or in a slide's script ("grey", "centre"), which the
#: slides module must know by that spelling to understand it (ADR-049).
IDENTIFIERS = {"cancelled", "practise", "colour", "grey", "centre"}
#: Where the database's own names are written.
SCHEMA = (Path("migrations"), Path("infrastructure", "orm.py"))


def _strings(path: Path) -> Iterator[tuple[int, str]]:
    """The strings in a Python file that are not docstrings, with their lines."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    documentation: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                documentation.add(id(first.value))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in documentation
        ):
            yield node.lineno, node.value


def _texts(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _texts(item)


def british(text: str) -> str | None:
    if text.strip() in IDENTIFIERS:
        return None
    found = BRITISH.search(text)
    return found.group(0) if found else None


def test_every_sentence_the_core_can_say_is_in_american_english() -> None:
    found = []
    for path in sorted(CORE.rglob("*.py")):
        relative = path.relative_to(CORE)
        if any(relative == place or place in relative.parents for place in SCHEMA):
            continue
        for line, text in _strings(path):
            if word := british(text):
                found.append(f"{relative}:{line}: {word}")
    assert found == []


def test_the_sample_course_is_in_american_english() -> None:
    files = sorted((CORE / "sample_course").rglob("*.json"))
    assert len(files) > 5
    found = [
        f"{path.relative_to(CORE)}: {word}"
        for path in files
        for text in _texts(json.loads(path.read_text(encoding="utf-8")))
        if (word := british(text))
    ]
    assert found == []


def test_what_the_model_is_told_asks_for_american_spelling() -> None:
    from adle_core.generation import prompts

    assert "American spelling" in prompts._WRITING_RULES
    scene = Path(prompts.__file__).read_text(encoding="utf-8")
    assert "spelled the American way" in scene


def test_the_check_reads_strings_and_not_comments(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        '"""A docstring may say colour."""\n'
        "# so may a comment: licence\n"
        'title = "Practise it"\n'
        'status = "cancelled"\n'
        "neighbour = 1\n",
        encoding="utf-8",
    )
    caught = [word for _, text in _strings(sample) if (word := british(text))]
    assert caught == ["Practise"]
