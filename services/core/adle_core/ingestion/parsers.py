"""Local parsers: file in, sections of plain text out.

No parser uploads anything, executes anything from the document, or follows
links or embedded references. Each returns an ``ExtractedDocument`` or raises
an ``IngestionError`` whose message a learner can act on.
"""

from __future__ import annotations

import re
import unicodedata
from importlib.metadata import version
from pathlib import Path
from typing import Any

from adle_core.ingestion.types import (
    HEADING_PATH_SEPARATOR,
    DocumentKind,
    ExtractedDocument,
    ExtractedSection,
    IngestionError,
    Limits,
    SectionKind,
)

#: Bumped whenever extraction output changes, so cached extractions can be invalidated.
PARSER_REVISION = "1"

LINE_BREAK = chr(10)
#: Unicode replacement character: what a decoder emits for bytes it cannot read.
REPLACEMENT_CHARACTER = chr(0xFFFD)

_MAX_TITLE = 300
_PATH_SEPARATOR = HEADING_PATH_SEPARATOR
_WHITESPACE_RUN = re.compile(r"[ \t\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalise extracted text without changing its meaning.

    NFC-normalises, removes control characters (keeping newlines and tabs),
    collapses runs of spaces, and limits consecutive blank lines to one.
    """
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = "".join(char for char in text if char in "\n\t" or unicodedata.category(char)[0] != "C")
    lines = [_WHITESPACE_RUN.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


class _HeadingPath:
    """Tracks the chain of headings above the current position, e.g. "Chapter 2 › Loss"."""

    def __init__(self) -> None:
        self._stack: list[tuple[int, str]] = []

    def enter(self, level: int, heading: str) -> None:
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        title = clean_text(heading).replace("\n", " ") or "Untitled"
        self._stack.append((level, title.replace(_PATH_SEPARATOR, " - ")))

    @property
    def level(self) -> int | None:
        return self._stack[-1][0] if self._stack else None

    @property
    def title(self) -> str | None:
        return _PATH_SEPARATOR.join(title for _, title in self._stack)[:_MAX_TITLE] or None


def _require_content(document: ExtractedDocument, limits: Limits) -> ExtractedDocument:
    if document.character_count == 0:
        raise IngestionError("empty_document", "No text could be found in the file.")
    if document.character_count > limits.max_characters:
        raise IngestionError(
            "file_too_large",
            "The document contains more text than Adle can import at once. "
            "Split it into smaller parts and import them separately.",
        )
    return document


# -- plain text ------------------------------------------------------------


def _decode(data: bytes) -> tuple[str, str | None]:
    """Decode text bytes, returning the text and a warning if the encoding was a guess."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), None
    try:
        return data.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        return (
            data.decode("cp1252", errors="replace"),
            "The file is not UTF-8; it was read as Windows-1252, so some characters may be wrong.",
        )


def parse_text(path: Path, limits: Limits) -> ExtractedDocument:
    text, warning = _decode(path.read_bytes())
    section = ExtractedSection(
        kind=SectionKind.DOCUMENT, text=clean_text(text), confidence=0.8 if warning else 1.0
    )
    return _require_content(
        ExtractedDocument(
            kind=DocumentKind.TEXT,
            sections=(section,),
            parser="text",
            parser_version=PARSER_REVISION,
            warnings=(warning,) if warning else (),
        ),
        limits,
    )


# -- markdown --------------------------------------------------------------


def _inline_text(children: list[Any]) -> str:
    """The text of an inline run, without emphasis, link, or image markup."""
    parts: list[str] = []
    for child in children:
        if child.type in ("softbreak", "hardbreak"):
            parts.append("\n")
        elif child.type != "image":
            parts.append(child.content)
    return "".join(parts)


def parse_markdown(path: Path, limits: Limits) -> ExtractedDocument:
    """Split a Markdown file into sections at its headings, keeping the heading path."""
    from markdown_it import MarkdownIt

    text, warning = _decode(path.read_bytes())
    tokens = MarkdownIt("commonmark").enable("table").parse(text)

    sections: list[ExtractedSection] = []
    headings = _HeadingPath()
    buffer: list[str] = []

    def flush() -> None:
        body = clean_text("\n\n".join(buffer))
        buffer.clear()
        if not body:
            return
        sections.append(
            ExtractedSection(
                kind=SectionKind.HEADING if headings.level is not None else SectionKind.DOCUMENT,
                text=body,
                title=headings.title,
                level=headings.level,
                confidence=0.8 if warning else 1.0,
            )
        )

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "heading_open":
            flush()
            heading = tokens[index + 1].content if index + 1 < len(tokens) else ""
            headings.enter(int(token.tag[1]), heading)
            index += 3  # heading_open, inline, heading_close
            continue
        if token.type == "inline":
            line = _inline_text(token.children or [])
            if line.strip():
                buffer.append(line)
        elif token.type in ("fence", "code_block") and token.content.strip():
            buffer.append(token.content.rstrip("\n"))
        index += 1
    flush()

    return _require_content(
        ExtractedDocument(
            kind=DocumentKind.MARKDOWN,
            sections=tuple(sections),
            parser="markdown-it-py",
            parser_version=f"{version('markdown-it-py')}+{PARSER_REVISION}",
            warnings=(warning,) if warning else (),
        ),
        limits,
    )


# -- PDF -------------------------------------------------------------------

#: A page with fewer characters than this is treated as having no usable text layer.
_MIN_PAGE_CHARACTERS = 20


def _garbled_ratio(text: str) -> float:
    """Share of characters that suggest a broken text layer (replacement or private-use)."""
    if not text:
        return 0.0
    bad = sum(
        1 for char in text if char == REPLACEMENT_CHARACTER or unicodedata.category(char) == "Co"
    )
    return bad / len(text)


def reflow_wrapped_lines(text: str) -> str:
    """Undo the hard line wrapping of a PDF page.

    A PDF stores lines, not paragraphs, so extracted sentences are broken at the
    right margin. A line that runs close to the full width was wrapped, and is
    joined to the next one; a short line (a heading, a list item, the end of a
    paragraph) keeps its break. Hyphenated words are left exactly as printed.
    """
    lines = text.splitlines()
    widest = max((len(line) for line in lines), default=0)
    # A wrapped line fills most of the measure. 80% leaves room for ragged-right
    # text while still treating a paragraph's short last line as an ending.
    threshold = max(40, int(widest * 0.8))
    reflowed: list[str] = []
    previous = ""
    for line in lines:
        wrapped = len(previous) >= threshold
        # A full-looking line that ends a sentence, followed by a capital, is more
        # likely the end of a paragraph than a wrap; keeping the break loses nothing.
        ends_sentence = previous.endswith((".", "!", "?", ":")) and line[:1].isupper()
        if reflowed and line and wrapped and not ends_sentence:
            reflowed[-1] = f"{reflowed[-1]} {line}"
        else:
            reflowed.append(line)
        previous = line
    return LINE_BREAK.join(reflowed)


def parse_pdf(path: Path, limits: Limits) -> ExtractedDocument:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise IngestionError(
                "encrypted_document",
                "This PDF is password-protected. Remove the password "
                "(for example by printing it to a new PDF) and import it again.",
            )
        page_count = len(reader.pages)
    except IngestionError:
        raise
    except (PyPdfError, ValueError, KeyError, OSError, RecursionError) as error:
        raise IngestionError(
            "malformed_document", "The PDF is damaged and could not be read."
        ) from error

    if page_count == 0:
        raise IngestionError("empty_document", "The PDF has no pages.")
    if page_count > limits.max_pages:
        raise IngestionError(
            "file_too_large",
            f"The PDF has {page_count} pages; the limit is {limits.max_pages}. "
            "Split it into parts and import them separately.",
        )

    sections: list[ExtractedSection] = []
    empty_pages: list[int] = []
    garbled_pages: list[int] = []
    unreadable_pages: list[int] = []
    for number in range(1, page_count + 1):
        try:
            raw = reader.pages[number - 1].extract_text() or ""
        except Exception:
            unreadable_pages.append(number)
            continue
        text = reflow_wrapped_lines(clean_text(raw))
        if len(text) < _MIN_PAGE_CHARACTERS:
            empty_pages.append(number)
            continue
        garbled = _garbled_ratio(text)
        if garbled > 0.05:
            garbled_pages.append(number)
        sections.append(
            ExtractedSection(
                kind=SectionKind.PAGE,
                text=text,
                page_number=number,
                confidence=max(0.2, 1.0 - 4 * garbled),
            )
        )

    if not sections:
        raise IngestionError(
            "scanned_document",
            "This PDF has no selectable text: it is probably a scan. Adle does not run text "
            "recognition (OCR) and never uploads files to do so. Convert it with an OCR tool "
            "first, or import the text in another format.",
        )

    warnings: list[str] = []
    if empty_pages:
        warnings.append(
            f"{len(empty_pages)} of {page_count} pages had no selectable text "
            f"(for example page {empty_pages[0]}). They may be images or scans and were skipped."
        )
    if garbled_pages:
        warnings.append(
            f"The text on {len(garbled_pages)} pages (for example page {garbled_pages[0]}) "
            "may be garbled. Check passages quoted from them."
        )
    if unreadable_pages:
        warnings.append(
            f"{len(unreadable_pages)} pages (for example page {unreadable_pages[0]}) "
            "could not be read and were skipped."
        )

    return _require_content(
        ExtractedDocument(
            kind=DocumentKind.PDF,
            sections=tuple(sections),
            parser="pypdf",
            parser_version=f"{version('pypdf')}+{PARSER_REVISION}",
            warnings=tuple(warnings),
        ),
        limits,
    )


# -- DOCX ------------------------------------------------------------------

_HEADING_STYLE = re.compile(r"^heading\s*(\d)$", re.IGNORECASE)


def _docx_heading_level(style_name: str) -> int | None:
    """Heading depth of a paragraph style. The document title sits above every heading."""
    match = _HEADING_STYLE.match(style_name)
    if match:
        return int(match.group(1))
    return 0 if style_name.lower() == "title" else None


def parse_docx(path: Path, limits: Limits) -> ExtractedDocument:
    """Split a Word document into sections at its heading-styled paragraphs."""
    import docx
    from docx.opc.exceptions import PackageNotFoundError
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(str(path))
    except (PackageNotFoundError, KeyError, ValueError, OSError) as error:
        raise IngestionError(
            "malformed_document", "The Word document is damaged and could not be opened."
        ) from error

    sections: list[ExtractedSection] = []
    headings = _HeadingPath()
    buffer: list[str] = []

    def flush() -> None:
        body = clean_text("\n\n".join(buffer))
        buffer.clear()
        if not body:
            return
        sections.append(
            ExtractedSection(
                kind=SectionKind.HEADING if headings.level is not None else SectionKind.DOCUMENT,
                text=body,
                title=headings.title,
                level=headings.level,
            )
        )

    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            style_name = (block.style.name if block.style is not None else None) or ""
            level = _docx_heading_level(style_name)
            if level is not None:
                flush()
                headings.enter(level, text)
            else:
                buffer.append(text)
        elif isinstance(block, Table):
            for row in block.rows:
                cells = [clean_text(cell.text).replace("\n", " ") for cell in row.cells]
                # Merged cells repeat; keep each distinct neighbour once.
                distinct = [c for i, c in enumerate(cells) if c and (i == 0 or c != cells[i - 1])]
                if distinct:
                    buffer.append(" | ".join(distinct))
    flush()

    return _require_content(
        ExtractedDocument(
            kind=DocumentKind.DOCX,
            sections=tuple(sections),
            parser="python-docx",
            parser_version=f"{version('python-docx')}+{PARSER_REVISION}",
        ),
        limits,
    )


PARSERS = {
    DocumentKind.TEXT: parse_text,
    DocumentKind.MARKDOWN: parse_markdown,
    DocumentKind.PDF: parse_pdf,
    DocumentKind.DOCX: parse_docx,
}


def parse_document(path: Path, kind: DocumentKind, limits: Limits) -> ExtractedDocument:
    return PARSERS[kind](path, limits)
