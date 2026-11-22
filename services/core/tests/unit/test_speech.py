"""Notation in narration is said in words, the way a teacher reads it aloud.

The lines below are ones a real model wrote in a lesson on a chapter of probability notes
(2026-11-22), which used to cost the lesson a second request each time.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter

from adle_core.generation.speech import spoken
from adle_core.lessons.ir import Spoken

SAID = [
    (
        r"is defined for every real number x as F_X(x) = P(X \le x).",
        "is defined for every real number x as F sub X of x equals P of (X is less than or "
        "equal to x).",
    ),
    (
        r"if a < b then F_X(a) \le F_X(b).",
        "if a is less than b then F sub X of a is less than or equal to F sub X of b.",
    ),
    (
        r"For x < 0, the density is zero. For x \ge 0, we integrate.",
        "For x less than 0, the density is zero. For x greater than or equal to 0, we integrate.",
    ),
    (
        r"The antiderivative of \lambda e^{-\lambda t} is -e^{-\lambda t}.",
        "The antiderivative of lambda e to the minus lambda t is minus e to the minus lambda t.",
    ),
    (
        r"gives -e^{-\lambda x} - (-1) = 1 - e^{-\lambda x}.",
        "gives minus e to the minus lambda x minus (minus 1) equals 1 minus e to the minus "
        "lambda x.",
    ),
    (
        r"Using the CDF, this is \Phi(2) - \Phi(-1).",
        "Using the CDF, this is Phi of 2 minus Phi of minus 1.",
    ),
    (
        r"the CDF is the integral of the density: F_X(x) = \int_{-\infty}^x f_X(t) dt.",
        "the CDF is the integral of the density: F sub X of x equals the integral from minus "
        "infinity to x of f sub X of t dt.",
    ),
    (
        r"To find the probability that X lies in an interval (a, b], we subtract.",
        "To find the probability that X lies in an interval (a, b], we subtract.",
    ),
    (r"so P(a < X \le b) = F(b) - F(a).", None),
]


@pytest.mark.parametrize(("written", "said"), SAID)
def test_a_line_with_notation_is_said_in_words(written: str, said: str | None) -> None:
    out = spoken(written)
    if said is not None:
        assert out == said
    for notation in ("\\", "$", "_", "^", "{", "}"):
        assert notation not in out


@pytest.mark.parametrize(
    ("written", "said"),
    [
        (r"$\frac{b-a}{10}$ of the time", "b minus a over 10 of the time"),
        (r"$\sqrt{2}$ and $\sqrt[3]{8}$", "the square root of 2 and the cube root of 8"),
        (r"$x^2 + y^3$", "x squared plus y cubed"),
        (r"$\sum_{i=1}^{n} x_i$", "the sum from i equals 1 to n of x sub i"),
        (r"$\lim_{x \to \infty} f(x) = 0$", "the limit as x goes to infinity of f of x equals 0"),
        (r"$\binom{n}{k}$ ways", "n choose k ways"),
        (r"$X \sim N(0, 1)$", "X is distributed as N of (0, 1)"),
        (r"$\bar{x}$ and $\hat{y}$", "x bar and y hat"),
        (r"$E[X] = \mu$", "E of X equals mu"),
        (r"$P(A \mid B)$", "P of (A given B)"),
        (r"$x/10$ in $\text{minutes}$", "x over 10 in minutes"),
        (
            r"$F(x) = \begin{cases} 0 & x < 0 \\ 1 & x \ge 0 \end{cases}$",
            "F of x equals 0 when x less than 0, 1 when x greater than or equal to 0",
        ),
    ],
)
def test_the_usual_notation_is_said_as_a_teacher_says_it(written: str, said: str) -> None:
    assert spoken(written) == said


def test_a_line_without_notation_is_left_as_it_was() -> None:
    for line in (
        "The x-axis shows time; a non-decreasing curve never falls.",
        "For x < 0 the density is zero.",
        "Half of 1/2 is a quarter.",
    ):
        assert spoken(line) == line


def test_words_joined_by_a_hyphen_stay_joined() -> None:
    said = spoken(r"A right-continuous $F$ on the x-axis has a p-value of $\alpha$.")
    assert said == "A right-continuous F on the x-axis has a p-value of alpha."


def test_a_line_with_a_link_or_markup_is_never_said_and_is_refused_as_it_was() -> None:
    for line in (
        r"Here z equals $w x + b$, see https://example.com/more",
        r"Read $x$ at www.example.com",
        r"Look <script>alert(1)</script> at $x$",
    ):
        assert spoken(line) == line


def test_a_command_it_does_not_know_is_said_by_its_name_and_nothing_is_left_of_it() -> None:
    assert spoken(r"the $\foo{x}$ of it") == "the foo x of it"
    assert spoken("a lone backslash \\ here {and} there") == "a lone backslash here and there"


def test_what_it_says_is_always_narration_the_lesson_takes() -> None:
    check = TypeAdapter(Spoken)
    for written, _ in SAID:
        check.validate_python(spoken(written))


def test_a_line_said_longer_than_a_caption_ends_at_a_sentence() -> None:
    written = (r"First $a \le b$. " * 40).strip()
    said = spoken(written)
    assert len(said) <= 700
    assert said.endswith(".")
