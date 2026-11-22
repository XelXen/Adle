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
#: Bumped when what a parser makes of the same file changes. "2": Word documents keep
#: their equations, the descriptions of their pictures, and their tables as tables (ADR-041).
PARSER_REVISION = "3"

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


#: A line of a table of contents: its title, dot leaders, and a page number.
_LEADERS = re.compile(r"(?:\.\s?){4,}")
#: A numbered heading: "5.2 The Cumulative Distribution Function", "3 Results".
_NUMBERED_HEADING = re.compile(
    r"^(?P<number>\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+(?P<title>[A-Z][^\n]{1,79})$"
)


def reflow_wrapped_lines(text: str) -> str:
    """Undo the hard line wrapping of a PDF page.

    A PDF stores lines, not paragraphs, so extracted sentences are broken at the
    right margin. A line that runs close to the full width was wrapped, and is
    joined to the next one; a short line (a heading, a list item, the end of a
    paragraph) keeps its break. Hyphenated words are left exactly as printed.
    A line of a table of contents is as wide as a wrapped one and is not one, and
    a numbered heading starts a line of its own.
    """
    lines = text.splitlines()
    widest = max((len(line) for line in lines), default=0)
    # A wrapped line fills most of the measure. 80% leaves room for ragged-right
    # text while still treating a paragraph's short last line as an ending.
    threshold = max(40, int(widest * 0.8))
    reflowed: list[str] = []
    previous = ""
    for line in lines:
        wrapped = len(previous) >= threshold and not _LEADERS.search(previous)
        # A full-looking line that ends a sentence, followed by a capital, is more
        # likely the end of a paragraph than a wrap; keeping the break loses nothing.
        ends_sentence = previous.endswith((".", "!", "?", ":")) and line[:1].isupper()
        heading = _is_numbered_heading(line)
        if reflowed and line and wrapped and not ends_sentence and not heading:
            reflowed[-1] = f"{reflowed[-1]} {line}"
        else:
            reflowed.append(line)
        previous = line
    return LINE_BREAK.join(reflowed)


def _is_numbered_heading(line: str) -> bool:
    found = _NUMBERED_HEADING.match(line.strip())
    if found is None or _LEADERS.search(line):
        return False
    title = found.group("title")
    # A title, not a sentence or a line of a calculation: mostly letters, no final stop.
    letters = sum(char.isalpha() for char in title)
    return not title.rstrip().endswith(".") and letters >= 0.6 * len(title.replace(" ", ""))


def _normalised(text: str) -> str:
    return " ".join(text.split()).casefold()


def _heading_offset(page_text: str, title: str) -> int | None:
    """Where a heading's own line is on its page: its number (if any) and its title alone
    on a line. A line of the table of contents names the title too, with dot leaders after
    it, and is passed over."""
    wanted = _normalised(title)
    offset = 0
    for line in page_text.splitlines(keepends=True):
        bare = _normalised(line)
        if bare and not _LEADERS.search(line):
            numbered = _NUMBERED_HEADING.match(line.strip())
            rest = _normalised(numbered.group("title")) if numbered else bare
            if rest == wanted or bare == wanted:
                return offset
        offset += len(line)
    return None


#: One heading of a paged document: its page (1-based), its depth, its title.
_PageHeading = tuple[int, int, str]


def _outline_headings(reader: Any) -> list[_PageHeading]:
    """The document's own outline (its bookmarks), as the program that made it wrote it."""
    found: list[_PageHeading] = []

    def walk(items: Any, level: int) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
                continue
            try:
                page = reader.get_destination_page_number(item)
            except Exception:  # noqa: S112 - a broken bookmark is not a broken document
                continue
            title = clean_text(str(getattr(item, "title", "") or "")).replace("\n", " ")
            if page is not None and page >= 0 and title:
                found.append((page + 1, min(level, 6), title[:_MAX_TITLE]))

    try:
        walk(reader.outline, 1)
    except Exception:  # an outline that cannot be read is no outline
        return []
    return found if len(found) >= 2 else []


def _numbered_headings(pages: list[tuple[int, str, float]]) -> list[_PageHeading]:
    """Without an outline: the lines numbered as headings are ("5.2 The Cumulative ..."),
    if there are at least three and they come in order."""
    found: list[tuple[tuple[int, ...], _PageHeading]] = []
    for number, text, _ in pages:
        for line in text.splitlines():
            if not _is_numbered_heading(line):
                continue
            matched = _NUMBERED_HEADING.match(line.strip())
            assert matched is not None
            key = tuple(int(part) for part in matched.group("number").split("."))
            if found and key <= found[-1][0]:
                continue
            found.append((key, (number, len(key), matched.group("title").strip())))
    return [heading for _, heading in found] if len(found) >= 3 else []


def _sections_by_heading(
    pages: list[tuple[int, str, float]], headings: list[_PageHeading]
) -> list[ExtractedSection]:
    """The pages cut where each heading begins. A heading that runs over several pages
    gives a section for each of them, so that a passage still says which page it is on."""
    texts = {number: (text, confidence) for number, text, confidence in pages}
    numbers = sorted(texts)
    placed: list[tuple[int, int, int, str]] = []
    for page, level, title in headings:
        # A bookmark to a page without text points at the next page that has some.
        landing = next((number for number in numbers if number >= page), None)
        if landing is None:
            continue
        offset = _heading_offset(texts[landing][0], title) if landing == page else 0
        placed.append((landing, offset or 0, level, title))
    if not placed:
        return []
    placed.sort(key=lambda heading: (heading[0], heading[1]))

    sections: list[ExtractedSection] = []
    first_page, first_offset = placed[0][0], placed[0][1]
    for number in numbers:
        text, confidence = texts[number]
        before = (
            text if number < first_page else text[:first_offset] if number == first_page else ""
        )
        if before.strip():
            sections.append(
                ExtractedSection(
                    kind=SectionKind.PAGE,
                    text=before.strip(),
                    page_number=number,
                    confidence=confidence,
                )
            )
    path = _HeadingPath()
    for index, (page, offset, level, title) in enumerate(placed):
        path.enter(level, title)
        if index + 1 < len(placed):
            end_page, end_offset = placed[index + 1][0], placed[index + 1][1]
        else:
            end_page, end_offset = numbers[-1], len(texts[numbers[-1]][0])
        pieces = 0
        for number in numbers:
            if number < page or number > end_page:
                continue
            text, confidence = texts[number]
            start = offset if number == page else 0
            stop = end_offset if number == end_page else len(text)
            piece = text[start:stop].strip()
            if not piece:
                continue
            pieces += 1
            sections.append(
                ExtractedSection(
                    kind=SectionKind.HEADING,
                    text=piece,
                    title=path.title,
                    level=level,
                    page_number=number,
                    confidence=confidence,
                )
            )
        if pieces == 0:
            # The heading, then the next one straight away: it is still a heading.
            sections.append(
                ExtractedSection(
                    kind=SectionKind.HEADING,
                    text=title,
                    title=path.title,
                    level=level,
                    page_number=page,
                    confidence=texts[page][1],
                )
            )
    return sections


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

    pages: list[tuple[int, str, float]] = []
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
        pages.append((number, text, max(0.2, 1.0 - 4 * garbled)))

    if not pages:
        raise IngestionError(
            "scanned_document",
            "This PDF has no selectable text: it is probably a scan. Adle does not run text "
            "recognition (OCR) and never uploads files to do so. Convert it with an OCR tool "
            "first, or import the text in another format.",
        )

    # Cut where the document's headings begin, so that what it covers can be read off
    # them: its own outline first, else the lines numbered as headings, else the pages.
    headings = _outline_headings(reader) or _numbered_headings(pages)
    sections = _sections_by_heading(pages, headings) if headings else []
    if not sections:
        sections = [
            ExtractedSection(
                kind=SectionKind.PAGE, text=text, page_number=number, confidence=confidence
            )
            for number, text, confidence in pages
        ]

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

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
_WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
#: The longest an equation or a picture's description is kept, in characters.
_MAX_INLINE = 600


def _local(element: Any) -> str:
    tag = element.tag if isinstance(element.tag, str) else ""
    return tag.rsplit("}", 1)[-1]


def _child(element: Any, name: str) -> Any:
    return next((child for child in element if _local(child) == name), None)


def _wrapped(text: str) -> str:
    """A part of an equation, in brackets when it is more than one symbol."""
    return text if len(text) <= 1 or text.isalnum() else f"({text})"


def omml_text(element: Any) -> str:
    """An Office Math equation written out in one line: x^2, (a+b)/c, √(x), ∑_(i=1)^n.

    Not a typesetter: enough of the structure survives to be searched for and quoted, and a
    reader can tell a fraction from a product. Anything not listed is read for its letters.
    """
    name = _local(element)

    def part(child_name: str) -> str:
        child = _child(element, child_name)
        return omml_text(child) if child is not None else ""

    def setting(properties: str, key: str, default: str) -> str:
        found = _child(element, properties)
        value = _child(found, key) if found is not None else None
        if value is None:
            return default
        return str(value.get(f"{_M}val", default))

    if name == "t":
        return element.text or ""
    if name == "f":
        return f"{_wrapped(part('num'))}/{_wrapped(part('den'))}"
    if name == "sSup":
        return f"{part('e')}^{_wrapped(part('sup'))}"
    if name == "sSub":
        return f"{part('e')}_{_wrapped(part('sub'))}"
    if name == "sSubSup":
        return f"{part('e')}_{_wrapped(part('sub'))}^{_wrapped(part('sup'))}"
    if name == "rad":
        degree = part("deg")
        inner = part("e")
        return f"root({degree}, {inner})" if degree else f"√{_wrapped(inner)}"
    if name == "nary":
        symbol = setting("naryPr", "chr", "∫")
        lower, upper = part("sub"), part("sup")
        limits = (f"_{_wrapped(lower)}" if lower else "") + (f"^{_wrapped(upper)}" if upper else "")
        return f"{symbol}{limits} {part('e')}"
    if name == "d":
        opening = setting("dPr", "begChr", "(")
        closing = setting("dPr", "endChr", ")")
        separator = setting("dPr", "sepChr", ",")
        inside = [omml_text(child) for child in element if _local(child) == "e"]
        return f"{opening}{separator.join(inside)}{closing}"
    if name == "func":
        return f"{part('fName')} {_wrapped(part('e'))}"
    if name.endswith("Pr"):
        # Properties say how a part is drawn, not what it is.
        return ""
    return "".join(omml_text(child) for child in element)


def _docx_inline_text(paragraph_element: Any) -> str:
    """A paragraph's text in document order: its runs and links, its equations written out,
    and each picture as what its description says it is."""
    pieces: list[str] = []

    def visit(element: Any) -> None:
        name = _local(element)
        namespace = element.tag.split("}", 1)[0] + "}" if isinstance(element.tag, str) else ""
        if namespace == _M and name in ("oMath", "oMathPara"):
            equation = " ".join(omml_text(element).split())
            if equation:
                pieces.append(f" {equation[:_MAX_INLINE]} ")
            return
        if namespace == _W and name == "t":
            pieces.append(element.text or "")
            return
        if namespace == _W and name == "tab":
            pieces.append("\t")
            return
        if namespace == _W and name in ("br", "cr"):
            pieces.append("\n")
            return
        if namespace == _W and name in ("drawing", "pict"):
            described = next(
                (
                    found.get("descr") or found.get("title")
                    for found in element.iter(f"{_WP}docPr")
                    if found.get("descr") or found.get("title")
                ),
                None,
            )
            if described:
                pieces.append(f" [Picture: {' '.join(described.split())[:_MAX_INLINE]}] ")
            return
        if namespace == _W and name in ("del", "instrText", "delText"):
            # Deleted text and the codes behind fields are not what the reader sees.
            return
        for child in element:
            visit(child)

    visit(paragraph_element)
    # Runs of spaces left around an equation or a picture are folded by ``clean_text``.
    return "".join(pieces).strip()


def _markdown_table(rows: list[list[str]]) -> str:
    """Rows of cell texts as a Markdown table, the first row as its header."""
    width = max(len(row) for row in rows)
    lines = []
    for index, row in enumerate(rows):
        cells = [cell.replace("|", "\\|") for cell in row] + [""] * (width - len(row))
        lines.append("| " + " | ".join(cells) + " |")
        if index == 0:
            lines.append("|" + " --- |" * width)
    return "\n".join(lines)


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
            text = clean_text(_docx_inline_text(block._p))
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
            rows: list[list[str]] = []
            for row in block.rows:
                cells: list[str] = []
                previous: Any = None
                for cell in row.cells:
                    # A merged cell is the same cell again: said once, then left empty.
                    same = previous is not None and cell._tc is previous._tc
                    words = " ".join(
                        _docx_inline_text(paragraph._p) for paragraph in cell.paragraphs
                    )
                    cells.append("" if same else " ".join(clean_text(words).split()))
                    previous = cell
                if any(cells):
                    rows.append(cells)
            if rows:
                buffer.append(_markdown_table(rows))
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
