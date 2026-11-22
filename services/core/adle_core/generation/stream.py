"""A lesson's answer read while it is being written: what it says before its parts, and then
each part as soon as the model has finished writing it (ADR-048).

The answer is one JSON object, written in order: ``{"title", "strategy", "sources",
"segments": [{...}, {...}, ...], "practice": [...], "voice": "..."}``. This finds where each
element of ``"segments"`` begins and ends as the text arrives, and hands over the text of
each one once its closing brace has come. Nothing is parsed here and nothing is guessed:
the text inside a string, escapes included, is never taken for structure, and what comes
before the first brace (a code fence, a sentence) is passed over. It is pure: no model, no
clock, no state but what it has been given.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The longest answer read: a lesson is about 15,000 characters, its bound far above that.
_MAX_CHARACTERS = 400_000


@dataclass
class Found:
    """What a piece of the answer completed."""

    #: The answer's own fields before its parts, as a JSON object: once, when the parts
    #: begin. ``None`` otherwise, and when the parts come first.
    header: str | None = None
    #: Each part whose writing this piece finished, as JSON text, in order.
    parts: list[str] = field(default_factory=list)


class PartStream:
    """Follows one answer as it is written. ``add`` each piece in order; ``start_again`` when
    another answer begins from its first word."""

    def __init__(self) -> None:
        self.start_again()

    def start_again(self) -> None:
        self._text = ""
        self._at = 0
        #: Where the answer's object begins; -1 until its brace has come.
        self._begun = -1
        self._depth = 0
        self._in_string = False
        self._escaped = False
        #: The last string closed inside the answer's own object, and where it began.
        self._last_string = ""
        self._last_string_at = -1
        self._string_at = -1
        #: The key whose value is being read in the answer's own object.
        self._key = ""
        self._key_at = -1
        self._in_parts = False
        self._part_at = -1
        self._parts_done = False
        #: How many parts have been handed over.
        self.count = 0

    @property
    def finished_parts(self) -> bool:
        """The list of parts has closed: every part has been handed over."""
        return self._parts_done

    def add(self, piece: str) -> Found:
        found = Found()
        if len(self._text) + len(piece) > _MAX_CHARACTERS:
            return found
        self._text += piece
        text = self._text
        while self._at < len(text) and not self._parts_done:
            index = self._at
            char = text[index]
            self._at += 1
            if self._in_string:
                if self._escaped:
                    self._escaped = False
                elif char == "\\":
                    self._escaped = True
                elif char == '"':
                    self._in_string = False
                    if self._depth == 1:
                        self._last_string = text[self._string_at + 1 : index]
                        self._last_string_at = self._string_at
                continue
            if self._begun < 0:
                # Whatever comes before the answer's object is not the answer.
                if char == "{":
                    self._begun = index
                    self._depth = 1
                continue
            if self._depth == 0:
                # The answer's object has closed: nothing after it is the answer.
                self._at = len(text)
                break
            if char == '"':
                self._in_string = True
                self._string_at = index
            elif char == ":" and self._depth == 1:
                self._key = self._last_string
                self._key_at = self._last_string_at
            elif char == "," and self._depth == 1:
                self._key = ""
            elif char in "{[":
                if char == "[" and self._depth == 1 and self._key == "segments":
                    self._in_parts = True
                    found.header = self._header()
                elif char == "{" and self._in_parts and self._depth == 2:
                    self._part_at = index
                self._depth += 1
            elif char in "}]":
                self._depth -= 1
                if self._in_parts and char == "}" and self._depth == 2 and self._part_at >= 0:
                    found.parts.append(text[self._part_at : index + 1])
                    self._part_at = -1
                    self.count += 1
                elif self._in_parts and char == "]" and self._depth == 1:
                    self._in_parts = False
                    self._parts_done = True
        return found

    def _header(self) -> str | None:
        """The answer's fields before ``"segments"``, closed as an object of their own."""
        if self._key_at <= self._begun:
            return None
        before = self._text[self._begun : self._key_at].rstrip()
        if before.endswith(","):
            before = before[:-1]
        return before + "}" if before.strip() != "{" else None
