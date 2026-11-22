"""Mathematics said in words, for narration that is read aloud.

A lesson's narration is spoken by a voice and shown as captions, so it must be words: a
voice reads ``F_X(x) = P(X \\le x)`` as "F underscore X, backslash le". A model asked for
words writes notation in it anyway, more often the more mathematical the subject: in the
first real lesson on a chapter of probability notes, twelve of twenty-five lines had some.
The lesson used to be refused for it and written again, a minute or two more, and the second
answer could fail somewhere else (it did).

So the core says the notation itself, the way a teacher reads it aloud: "F sub X of x
equals P of (X is less than or equal to x)", "e to the minus lambda x", "the integral from
0 to x of". Only a line with notation in it is touched (a dollar sign, a backslash, ``_``,
``^``, ``{`` or ``}``), and what comes out has none of those. It is pure: no model, no
state.
"""

from __future__ import annotations

import re

from adle_core.lessons.ir import is_plain_text

#: Notation that a voice would read out character by character.
_NOTATION = re.compile(r"[$\\_^{}]")

#: Mathematics written with its own symbols (a model writes "∫" as often as "\int"), as the
#: commands of TeX that say the same. Written by code point: several look like letters.
#: Figures use it too, so that what they set is what the player's TeX is sure to know.
UNICODE_TEX = {
    chr(0x222B): r" \int ",
    chr(0x2211): r" \sum ",
    chr(0x220F): r" \prod ",
    chr(0x221A): r" \sqrt ",
    chr(0x221E): r" \infty ",
    chr(0x2264): r" \le ",
    chr(0x2265): r" \ge ",
    chr(0x2260): r" \ne ",
    chr(0x2248): r" \approx ",
    chr(0x2192): r" \to ",
    chr(0x2208): r" \in ",
    chr(0x00B1): r" \pm ",
    chr(0x00D7): r" \times ",
    chr(0x00B7): r" \cdot ",
    chr(0x2202): r" \partial ",
    chr(0x2207): r" \nabla ",
    chr(0x2212): "-",
}
for _name, _point in (
    ("alpha", 0x3B1), ("beta", 0x3B2), ("gamma", 0x3B3), ("delta", 0x3B4),
    ("epsilon", 0x3B5), ("theta", 0x3B8), ("lambda", 0x3BB), ("mu", 0x3BC),
    ("pi", 0x3C0), ("rho", 0x3C1), ("sigma", 0x3C3), ("tau", 0x3C4), ("phi", 0x3C6),
    ("chi", 0x3C7), ("psi", 0x3C8), ("omega", 0x3C9), ("Gamma", 0x393), ("Delta", 0x394),
    ("Theta", 0x398), ("Lambda", 0x39B), ("Pi", 0x3A0), ("Sigma", 0x3A3), ("Phi", 0x3A6),
    ("Psi", 0x3A8), ("Omega", 0x3A9),
):  # fmt: skip
    UNICODE_TEX[chr(_point)] = " \\" + _name + " "

_PIECE = re.compile(r"\\[A-Za-z]+|\\[^A-Za-z]|[{}^_&\[\]()]|[A-Za-z]+|\d+(?:\.\d+)?|\s+|.", re.S)

_GREEK = {
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta",
    "vartheta", "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "varpi", "rho", "varrho",
    "sigma", "varsigma", "tau", "upsilon", "phi", "varphi", "chi", "psi", "omega",
    "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega",
}  # fmt: skip

#: Functions, said by name: a bracket right after one is "of".
_FUNCTIONS = {
    "log": "log", "ln": "natural log", "lg": "log", "exp": "exp", "sin": "sine",
    "cos": "cosine", "tan": "tangent", "sec": "secant", "csc": "cosecant", "cot": "cotangent",
    "arcsin": "arcsine", "arccos": "arccosine", "arctan": "arctangent", "sinh": "hyperbolic sine",
    "cosh": "hyperbolic cosine", "tanh": "hyperbolic tangent", "det": "determinant",
    "Pr": "P", "Var": "Var", "Cov": "Cov", "gcd": "gcd", "arg": "arg", "deg": "degree",
}  # fmt: skip

#: Words of plain text that are functions too when a bracket follows at once: "Var(X)".
_FUNCTION_WORDS = {"log", "ln", "exp", "sin", "cos", "tan", "Var", "Cov", "Pr", "Corr", "SD"}

_SAID = {
    "le": "is less than or equal to", "leq": "is less than or equal to",
    "leqslant": "is less than or equal to", "ge": "is greater than or equal to",
    "geq": "is greater than or equal to", "geqslant": "is greater than or equal to",
    "lt": "is less than", "gt": "is greater than", "ll": "is much less than",
    "gg": "is much greater than", "ne": "is not equal to", "neq": "is not equal to",
    "approx": "is approximately", "simeq": "is approximately", "equiv": "is equivalent to",
    "sim": "is distributed as", "propto": "is proportional to", "cong": "is congruent to",
    "to": "goes to", "rightarrow": "goes to", "longrightarrow": "goes to",
    "mapsto": "maps to", "Rightarrow": "implies", "implies": "implies",
    "Longrightarrow": "implies", "iff": "if and only if", "Leftrightarrow": "if and only if",
    "infty": "infinity", "in": "in", "notin": "not in", "subset": "a subset of",
    "subseteq": "a subset of", "supset": "a superset of", "cup": "union", "cap": "intersect",
    "setminus": "minus", "emptyset": "the empty set", "varnothing": "the empty set",
    "cdot": "times", "times": "times", "div": "divided by", "pm": "plus or minus",
    "mp": "minus or plus", "ast": "times", "circ": "composed with",
    "ldots": "and so on", "cdots": "and so on", "dots": "and so on", "vdots": "and so on",
    "partial": "partial", "nabla": "the gradient", "forall": "for all", "exists": "there is",
    "neg": "not", "lnot": "not", "land": "and", "wedge": "and", "lor": "or", "vee": "or",
    "mid": "given", "perp": "is perpendicular to", "parallel": "is parallel to",
    "angle": "angle", "triangle": "triangle", "degree": "degrees", "prime": "prime",
    "ell": "l", "hbar": "h bar", "max": "the maximum", "min": "the minimum",
    "sup": "the supremum", "inf": "the infimum", "argmax": "the arg max", "argmin": "the arg min",
}  # fmt: skip

#: Commands whose argument is said as it is.
_WRAPPERS = {
    "text", "textrm", "textit", "textbf", "emph", "mathrm", "mathit", "mathbf", "mathsf",
    "mathtt", "mathcal", "mathbb", "mathfrak", "mathscr", "boldsymbol", "bm", "operatorname",
    "mbox", "textnormal",
}  # fmt: skip

#: Accents, and how a teacher says the letter under one.
_ACCENTS = {
    "hat": "{} hat", "widehat": "{} hat", "bar": "{} bar", "overline": "{} bar",
    "tilde": "{} tilde", "widetilde": "{} tilde", "vec": "vector {}", "dot": "{} dot",
    "ddot": "{} double dot", "underline": "{}", "overrightarrow": "vector {}",
}  # fmt: skip

#: Commands that say nothing: spacing, sizes, styles.
_SILENT = {
    "left", "right", "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr", "biggl",
    "biggr", "displaystyle", "textstyle", "scriptstyle", "limits", "nolimits", "quad",
    "qquad", "middle", "phantom", "nonumber", "notag", "label",
}  # fmt: skip

#: After \\left, \\right and the sizes: a bracket that is kept, or a delimiter that is not.
_SIZED = {"left", "right", "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr"}

_LIMITS = {"int": "the integral", "iint": "the double integral", "oint": "the integral",
           "sum": "the sum", "prod": "the product", "bigcup": "the union",
           "bigcap": "the intersection"}  # fmt: skip

_ESCAPED = {"\\{": " ", "\\}": " ", "\\%": " percent ", "\\$": " dollars ", "\\&": " and ",
            "\\#": " number ", "\\_": " ", "\\|": " ", "\\\\": ", "}  # fmt: skip

_MAX = 700

_RELATION = r"(?=less |greater |not equal |approximately |equivalent |in )"
_LOOSE_IS = re.compile(
    r"\b(for|with|when|where|all|any|each|every)\s+(\S+)\s+is\s+" + _RELATION, re.IGNORECASE
)
_CHAINED_IS = re.compile(r"\b(than|to)\s+(\S+)\s+is\s+" + _RELATION)

#: Words that a single letter is joined to by a hyphen: "x-axis", "p-value", "t-test".
_COMPOUNDS = {
    "axis", "axes", "intercept", "intercepts", "coordinate", "coordinates", "value", "values",
    "plane", "score", "scores", "test", "tests", "statistic", "distribution", "table",
    "direction", "component", "th", "shaped",
}  # fmt: skip

#: Symbols written as themselves, said.
_SYMBOLS = {
    "≤": " is less than or equal to ", "≥": " is greater than or equal to ",
    "≠": " is not equal to ", "≈": " is approximately ", "\u2212": " minus ",
    "\u00d7": " times ",
    "·": " times ", "∞": " infinity ", "→": " goes to ", "∈": " in ", "±": " plus or minus ",
}  # fmt: skip


def spoken(text: str) -> str:
    """``text`` with any notation in it said in words; text without notation as it was."""
    has_symbols = any(char in UNICODE_TEX for char in text)
    if not (_NOTATION.search(text) or has_symbols) or not is_plain_text(text):
        # A line with a link or markup in it is refused as it was written, never said.
        return text
    written = "".join(UNICODE_TEX.get(char, char) for char in text.replace("$", " "))
    reader = _Reader(_PIECE.findall(written))
    said = _tidy("".join(reader.read()[0]))
    # "For x is less than 0" is said "for x less than 0", and "a is less than X is less
    # than b" with one "is".
    said = _LOOSE_IS.sub(r"\1 \2 ", said)
    said = _CHAINED_IS.sub(r"\1 \2 ", said)
    if not said:
        return text
    if len(said) > _MAX:
        # Said in words a line can grow past what a caption holds: end at a sentence.
        cut = said[:_MAX]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        said = cut[: end + 1] if end > 0 else cut.rsplit(" ", 1)[0]
    return said


def _operand(piece: str) -> bool:
    """A number, a single letter, or a bracket: what a division sign stands between."""
    return (
        piece[:1].isdigit()
        or (len(piece) == 1 and piece.isalpha())
        or piece in ("(", ")", "{", "}")
    )


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,;:!?)\]])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    text = re.sub(r"(,\s*){2,}", ", ", text)
    return text.strip()


def _words(pieces: list[str]) -> str:
    return _tidy("".join(pieces))


class _Reader:
    """Reads a stream of pieces, plain words and TeX alike, and says each in words."""

    def __init__(self, pieces: list[str]) -> None:
        self.pieces = pieces
        self.at = 0
        #: What was said last can take an argument in brackets: "F(x)" is "F of x".
        self.applies = False
        #: Within cases, "&" is "when": "0 when x is less than 0".
        self.cases = 0

    # -- the stream -------------------------------------------------------------------------

    def _next(self, skip_space: bool = True) -> str | None:
        while self.at < len(self.pieces):
            piece = self.pieces[self.at]
            if skip_space and piece.isspace():
                self.at += 1
                continue
            return piece
        return None

    def read(self, stops: str = "") -> tuple[list[str], str | None]:
        """What is said up to the first of ``stops`` (a group nested in it is read whole by
        ``one``), and which of them ended it: None at the end of the text."""
        said: list[str] = []
        while self.at < len(self.pieces):
            piece = self.pieces[self.at]
            self.at += 1
            if len(piece) == 1 and piece in stops:
                return said, piece
            said.extend(self.one(piece))
        return said, None

    def argument(self) -> str:
        """One argument of a command, a power or an index: a {group}, or the next piece."""
        piece = self._next()
        if piece is None:
            return ""
        self.at += 1
        if piece == "{":
            return _words(self.read("}")[0])
        if piece == "-" and (following := self._next()) is not None:
            # A minus sign and what it is the minus of, as in x^-1.
            self.at += 1
            return "minus " + _words(self.one(following))
        return _words(self.one(piece))

    # -- one piece --------------------------------------------------------------------------

    def one(self, piece: str) -> list[str]:
        if piece.isspace():
            return [" "]
        if piece.startswith("\\"):
            return self.command(piece)
        if piece == "{":
            inner, _ = self.read("}")
            return [" ", *inner, " "]
        if piece == "}":
            return []
        if piece == "^":
            return self.power()
        if piece == "_":
            index = self.argument()
            self.applies = True
            return [f" sub {index} "] if index else []
        if piece == "&":
            return [" when "] if self.cases else [" "]
        if piece == "'":
            self.applies = True
            return [" prime "]
        if piece in "([":
            return self.bracket(piece)
        if piece in ")]":
            self.applies = False
            return [")" if piece == ")" else "]"]
        if piece[0].isalpha():
            self.applies = len(piece) == 1 or piece in _FUNCTION_WORDS
            return [piece]
        if piece[0].isdigit():
            self.applies = False
            said = [piece]
            if self._peek_is("("):
                said.append(" times ")
            return said
        self.applies = False
        return [self.operator(piece)]

    def _peek_is(self, wanted: str) -> bool:
        return self.at < len(self.pieces) and self.pieces[self.at] == wanted

    def operator(self, piece: str) -> str:
        if piece == "=":
            return " equals "
        if piece == "<":
            return " is less than "
        if piece == ">":
            return " is greater than "
        if piece == "+":
            return " plus "
        if piece == "*":
            return " times "
        if piece == "|":
            return " given "
        if piece == "-":
            before = self.pieces[self.at - 2] if self.at >= 2 else ""
            after = self.pieces[self.at] if self.at < len(self.pieces) else ""
            # Between two words it joins them: "non-decreasing", "x-axis". A command
            # before it ("\to-") is not a word.
            words = before[-1:].isalpha() and after[:1].isalpha() and before[:1] != "\\"
            if words and ((len(before) > 1 and len(after) > 1) or after.lower() in _COMPOUNDS):
                return "-"
            return " minus "
        if piece == "/":
            # Between two things divided, as in "x/10"; anywhere else it stays.
            before = self.pieces[self.at - 2] if self.at >= 2 else ""
            after = self.pieces[self.at] if self.at < len(self.pieces) else ""
            if _operand(before) and _operand(after):
                return " over "
            return "/"
        return _SYMBOLS.get(piece, piece)

    def bracket(self, opening: str) -> list[str]:
        applies = self.applies
        self.applies = False
        # Closed by either bracket: an interval may be half open, "(a, b]".
        inner, closing = self.read(")]")
        content = _words(inner)
        closed = (closing or "") + " "
        simple = len(content.split()) <= 2 and "," not in content
        if applies:
            # "F(x)" is "F of x"; brackets around more than one thing are kept.
            return [" of ", content, " "] if simple else [" of (", content, closed]
        return [" " + opening, content, closed]

    def power(self) -> list[str]:
        exponent = self.argument()
        self.applies = False
        if exponent in ("2",):
            return [" squared "]
        if exponent in ("3",):
            return [" cubed "]
        if exponent in ("T", "top", "intercal"):
            return [" transpose "]
        if exponent in ("prime", "'"):
            return [" prime "]
        return [f" to the {exponent} "] if exponent else []

    def command(self, piece: str) -> list[str]:
        if piece in _ESCAPED:
            self.applies = False
            return [_ESCAPED[piece]]
        name = piece[1:]
        if not name.isalpha():
            # \, \; \: \! and the like: a space.
            return [" "]
        if name in _GREEK:
            self.applies = True
            return [f" {name} "]
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            top, bottom = self.argument(), self.argument()
            self.applies = False
            return [f" {top} over {bottom} "]
        if name == "sqrt":
            degree = ""
            if self._next() == "[":
                self.at += 1
                degree = _words(self.read("]")[0])
            under = self.argument()
            self.applies = False
            if degree in ("", "2"):
                return [f" the square root of {under} "]
            if degree == "3":
                return [f" the cube root of {under} "]
            return [f" the {degree}th root of {under} "]
        if name in ("binom", "dbinom", "tbinom", "choose"):
            top, bottom = self.argument(), self.argument()
            self.applies = False
            return [f" {top} choose {bottom} "]
        if name in _LIMITS:
            return self.limits(_LIMITS[name])
        if name == "lim":
            below = self.subscript()
            self.applies = False
            return [f" the limit as {below} of "] if below else [" the limit of "]
        if name in ("max", "min", "sup", "inf", "argmax", "argmin") and self._next() == "_":
            below = self.subscript()
            self.applies = False
            return [f" {_SAID[name]} over {below} of "]
        if name in _WRAPPERS:
            inner = self.argument()
            self.applies = len(inner) == 1
            return [f" {inner} "]
        if name in _ACCENTS:
            inner = self.argument()
            self.applies = True
            return [" " + _ACCENTS[name].format(inner) + " "]
        if name in ("begin", "end"):
            environment = self.argument()
            if environment == "cases":
                self.cases += 1 if name == "begin" else -1
            if name == "begin" and environment == "array":
                self.argument()  # the columns' alignment
            self.applies = False
            return [" "]
        if name in _SIZED:
            following = self._next(skip_space=False)
            if following is not None and following in ".|":
                self.at += 1
            return []
        if name in _SILENT:
            return [" "]
        if name in _FUNCTIONS:
            self.applies = True
            return [f" {_FUNCTIONS[name]} "]
        if name in _SAID:
            self.applies = False
            return [f" {_SAID[name]} "]
        # A command this does not know: its name is the nearest thing to saying it.
        self.applies = False
        return [f" {name} "]

    def subscript(self) -> str:
        if self._next() != "_":
            return ""
        self.at += 1
        return self.argument()

    def limits(self, what: str) -> list[str]:
        below = above = ""
        for _ in range(2):
            mark = self._next()
            if mark == "_" and not below:
                self.at += 1
                below = self.argument()
            elif mark == "^" and not above:
                self.at += 1
                above = self.argument()
        self.applies = False
        if below and above:
            return [f" {what} from {below} to {above} of "]
        if below:
            return [f" {what} over {below} of "]
        return [f" {what} of "]
