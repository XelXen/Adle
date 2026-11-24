"""One page of a PDF, drawn as a picture to be read by a model that sees pictures (ADR-060).

Runs in the parser worker, never in the core: the file is the learner's, from anywhere, and
PDFium reads it. The picture is gray, at 150 dots to the inch, which is what reading a page
needs (measured on 2026-11-24: typed and handwritten pages read word for word), and a PNG
made here from PDFium's pixels, so that nothing else is needed to make one.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from adle_core.ingestion.types import IngestionError

#: How finely a page is drawn.
DOTS_PER_INCH = 150
#: The longest side of a picture, in pixels: a page larger than A3 is drawn smaller, so
#: that no page makes a picture a model is not sent.
LONGEST_SIDE = 2400


def _png(width: int, height: int, pixels: bytes, stride: int) -> bytes:
    """A gray PNG of ``height`` rows of ``width`` bytes, each row ``stride`` apart."""
    rows = b"".join(b"\x00" + pixels[row * stride : row * stride + width] for row in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows, 6))
        + chunk(b"IEND", b"")
    )


def page_picture(path: Path, page: int) -> bytes:
    """The page, 1-based, as a gray PNG."""
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as error:
        raise IngestionError("malformed_document", "The PDF could not be opened.") from error
    try:
        if not 1 <= page <= len(document):
            raise IngestionError("malformed_document", "The PDF has no such page.")
        sheet = document[page - 1]
        width, height = sheet.get_size()
        scale = DOTS_PER_INCH / 72
        if max(width, height) * scale > LONGEST_SIDE:
            scale = LONGEST_SIDE / max(width, height)
        bitmap = sheet.render(scale=scale, grayscale=True)
        return _png(bitmap.width, bitmap.height, bytes(bitmap.buffer), bitmap.stride)
    finally:
        document.close()
