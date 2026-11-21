"""What may be written to the log about an error.

The log is a file the learner is invited to show to someone else. The text of an
exception can hold what they typed, what a document says, or the values of a database
statement, so it never goes in: only what kind of error it was, and where in Adle it
happened.
"""

from __future__ import annotations

import traceback


def where(error: BaseException) -> str:
    """The frames an error passed through and the type of each error in its chain.

    No message, no source line (a line of code can hold a literal), no local values.
    """
    lines: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        lines.append(type(current).__name__)
        for frame in traceback.extract_tb(current.__traceback__):
            lines.append(f"  {frame.filename}:{frame.lineno} in {frame.name}")
        current = current.__cause__ or current.__context__
        if current is not None:
            lines.append("caused by")
    return "\n".join(lines)
