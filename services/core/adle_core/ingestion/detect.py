"""Decide what kind of document a file is, from its content as well as its name.

A file's extension is a claim, not a fact. A ``.pdf`` that is really an
executable, or a ``.txt`` that is binary, is rejected here before any parser
sees it.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from adle_core.ingestion.types import (
    DocumentKind,
    IngestionError,
    Limits,
    too_large,
    unsupported_type,
)

_EXTENSIONS: dict[str, DocumentKind] = {
    ".pdf": DocumentKind.PDF,
    ".docx": DocumentKind.DOCX,
    ".md": DocumentKind.MARKDOWN,
    ".markdown": DocumentKind.MARKDOWN,
    ".txt": DocumentKind.TEXT,
    ".text": DocumentKind.TEXT,
}

#: Formats people commonly try, with a specific hint for each.
_KNOWN_UNSUPPORTED: dict[str, str] = {
    ".doc": "Older Word documents (.doc) are not supported; save it as .docx.",
    ".pptx": "PowerPoint files are not supported; export the slides as a PDF.",
    ".ppt": "PowerPoint files are not supported; export the slides as a PDF.",
    ".odt": "OpenDocument files are not supported; export it as .docx or PDF.",
    ".rtf": "Rich Text files are not supported; save it as .docx or .txt.",
    ".epub": "E-books are not supported yet.",
    ".html": "Web pages are not supported; save the page as a PDF.",
    ".htm": "Web pages are not supported; save the page as a PDF.",
    ".png": "Images are not supported: Adle does not run text recognition (OCR).",
    ".jpg": "Images are not supported: Adle does not run text recognition (OCR).",
    ".jpeg": "Images are not supported: Adle does not run text recognition (OCR).",
}

_SNIFF_BYTES = 8 * 1024


def _looks_like_text(sample: bytes) -> bool:
    if b"\x00" in sample:
        # UTF-16 text contains NULs; accept it only with a byte-order mark.
        return sample.startswith((b"\xff\xfe", b"\xfe\xff"))
    control = sum(1 for byte in sample if byte < 9 or 13 < byte < 32)
    return control <= len(sample) // 100


def detect_kind(path: Path, display_name: str, limits: Limits) -> DocumentKind:
    """Return the document kind, or raise an ``IngestionError`` the learner can act on."""
    extension = Path(display_name).suffix.lower()
    if extension in _KNOWN_UNSUPPORTED:
        raise unsupported_type(_KNOWN_UNSUPPORTED[extension])
    claimed = _EXTENSIONS.get(extension)
    if claimed is None:
        shown = f"'{extension}' files are" if extension else "Files without an extension are"
        raise unsupported_type(f"{shown} not supported.")

    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            sample = handle.read(_SNIFF_BYTES)
    except OSError as error:
        raise IngestionError(
            "file_unreadable", "The file could not be opened. It may have been moved or deleted."
        ) from error

    if size == 0:
        raise IngestionError("empty_document", "The file is empty.")
    is_text_kind = claimed in (DocumentKind.TEXT, DocumentKind.MARKDOWN)
    ceiling = limits.max_text_file_bytes if is_text_kind else limits.max_file_bytes
    if size > ceiling:
        raise too_large(ceiling)

    if claimed is DocumentKind.PDF:
        # The header may be preceded by a few junk bytes in files produced by old tools.
        if b"%PDF-" not in sample[:1024]:
            raise unsupported_type("The file is named .pdf but is not a PDF document.")
    elif claimed is DocumentKind.DOCX:
        if not sample.startswith(b"PK"):
            raise unsupported_type("The file is named .docx but is not a Word document.")
        try:
            with zipfile.ZipFile(path) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise unsupported_type("The file is named .docx but is not a Word document.")
        except zipfile.BadZipFile as error:
            raise IngestionError(
                "malformed_document", "The Word document is damaged and could not be opened."
            ) from error
    elif not _looks_like_text(sample):
        raise unsupported_type("The file does not contain readable text.")

    return claimed
