"""Convert DOCX document structure into conservative ATX Markdown."""

from __future__ import annotations

import re
from io import BytesIO

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

__all__ = ["docx_to_markdown"]


_HEADING_STYLE = re.compile(r"^(?:Heading|标题)\s+([1-9])$")
_BLANK_LINES = re.compile(r"\n{3,}")


def _paragraph_markdown(paragraph: Paragraph) -> str:
    text = paragraph.text
    match = _HEADING_STYLE.fullmatch(paragraph.style.name or "")
    level = int(match.group(1)) if match else None
    if level is None:
        properties = paragraph._p.pPr
        outline = properties.find(qn("w:outlineLvl")) if properties is not None else None
        if outline is not None:
            try:
                outline_level = int(outline.get(qn("w:val")))
            except (TypeError, ValueError):
                outline_level = -1
            if 0 <= outline_level <= 8:
                level = outline_level + 1
    return f"{'#' * level} {text}" if level is not None else text


def _cell_text(cell) -> str:
    text = "\n".join(paragraph.text for paragraph in cell.paragraphs)
    return re.sub(r"\r\n|\r|\n", " ", text).replace("|", " ")


def _table_markdown(table: Table) -> str:
    rows = [[_cell_text(cell) for cell in row.cells] for row in table.rows]
    if not rows:
        return "|  |\n| --- |"
    width = max((len(row) for row in rows), default=0)
    if width == 0:
        return "|  |\n| --- |"
    rendered = []
    for index, row in enumerate(rows):
        padded = row + [""] * (width - len(row))
        rendered.append("| " + " | ".join(padded) + " |")
        if index == 0:
            rendered.append("| " + " | ".join("---" for _ in range(width)) + " |")
    return "\n".join(rendered)


def docx_to_markdown(data: bytes) -> str:
    """Convert DOCX bytes in body order; raises ValueError with a docx failure stage."""
    try:
        document = Document(BytesIO(data))
    except Exception as exc:
        raise ValueError("docx 打开阶段失败：文件不是可读取的 DOCX 包（可能损坏或加密）") from exc

    try:
        blocks: list[str] = []
        body = document.element.body
        for child in body:
            if child.tag == qn("w:p"):
                blocks.append(_paragraph_markdown(Paragraph(child, document._body)))
            elif child.tag == qn("w:tbl"):
                blocks.append(_table_markdown(Table(child, document._body)))
        result = _BLANK_LINES.sub("\n\n", "\n\n".join(blocks))
    except Exception as exc:
        raise ValueError("docx 转换阶段失败：无法读取段落或表格结构") from exc
    if not result.strip():
        raise ValueError("docx 文本抽取阶段失败：docx 未提取到有效文本")
    return result
