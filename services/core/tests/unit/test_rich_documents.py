"""What a document holds besides its running text: equations, pictures, tables (ADR-041)."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from lxml import etree

from adle_core.ingestion.extract import extract_in_process
from adle_core.ingestion.parsers import PARSER_REVISION, omml_text

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
#: The smallest picture there is: one pixel.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def math(xml: str) -> etree._Element:
    return etree.fromstring(f'<m:oMath xmlns:m="{M}">{xml}</m:oMath>')


def run(text: str) -> str:
    return f"<m:r><m:t>{text}</m:t></m:r>"


def test_an_equation_is_written_out_in_a_line() -> None:
    fraction = f"<m:f><m:num>{run('a+b')}</m:num><m:den>{run('c')}</m:den></m:f>"
    power = f"<m:sSup><m:e>{run('x')}</m:e><m:sup>{run('2')}</m:sup></m:sSup>"
    assert omml_text(math(fraction + run("+") + power)) == "(a+b)/c+x^2"
    lower = f"<m:sSub><m:e>{run('w')}</m:e><m:sub>{run('1')}</m:sub></m:sSub>"
    assert omml_text(math(lower)) == "w_1"
    root = f"<m:rad><m:radPr/><m:deg/><m:e>{run('x+1')}</m:e></m:rad>"
    assert omml_text(math(root)) == "√(x+1)"
    total = (
        f'<m:nary><m:naryPr><m:chr m:val="∑"/></m:naryPr><m:sub>{run("i=1")}</m:sub>'
        f"<m:sup>{run('n')}</m:sup><m:e>{run('x_i')}</m:e></m:nary>"
    )
    assert omml_text(math(total)) == "∑_(i=1)^n x_i"
    bracket = f"<m:d><m:dPr/><m:e>{run('a')}</m:e><m:e>{run('b')}</m:e></m:d>"
    assert omml_text(math(bracket)) == "(a,b)"
    function = f"<m:func><m:fName>{run('sin')}</m:fName><m:e>{run('x')}</m:e></m:func>"
    assert omml_text(math(function)) == "sin x"


def rich_document(folder: Path) -> Path:
    import docx
    from docx.oxml import parse_xml
    from docx.shared import Inches

    document = docx.Document()
    document.add_heading("Weights", level=1)
    sentence = document.add_paragraph("The sum is ")
    fraction = f"<m:f><m:num>{run('a+b')}</m:num><m:den>{run('c')}</m:den></m:f>"
    sentence._p.append(parse_xml(f'<m:oMath xmlns:m="{M}">{fraction}</m:oMath>'))
    sentence.add_run(" for every input.")

    picture = document.add_paragraph().add_run().add_picture(io.BytesIO(PNG), width=Inches(1))
    picture._inline.docPr.set("descr", "A neuron with two inputs and one output")

    table = document.add_table(rows=3, cols=2)
    for row, (term, meaning) in enumerate(
        [("Term", "Meaning"), ("Weight", "How much an input counts"), ("", "")]
    ):
        table.cell(row, 0).text = term
        table.cell(row, 1).text = meaning
    merged = table.cell(2, 0).merge(table.cell(2, 1))
    merged.text = "Both | together decide the output"

    path = folder / "rich.docx"
    document.save(str(path))
    return path


def test_a_word_document_keeps_its_equations_pictures_and_tables(tmp_path: Path) -> None:
    document = extract_in_process(rich_document(tmp_path), "rich.docx")
    (section,) = document.sections
    assert section.title == "Weights"
    assert "The sum is (a+b)/c for every input." in section.text
    assert "[Picture: A neuron with two inputs and one output]" in section.text
    # A table is a table, with its first row as its header; a merged cell is said once,
    # and a bar inside a cell does not end it.
    assert (
        "| Term | Meaning |\n"
        "| --- | --- |\n"
        "| Weight | How much an input counts |\n"
        "| Both \\| together decide the output | |"
    ) in section.text
    assert document.parser_version.endswith(f"+{PARSER_REVISION}")
