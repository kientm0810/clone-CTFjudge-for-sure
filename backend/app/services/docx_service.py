from collections.abc import Iterator
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
BODY_TAG = f"{{{WORD_NAMESPACE}}}body"
PARAGRAPH_TAG = f"{{{WORD_NAMESPACE}}}p"
TABLE_TAG = f"{{{WORD_NAMESPACE}}}tbl"
ROW_TAG = f"{{{WORD_NAMESPACE}}}tr"
CELL_TAG = f"{{{WORD_NAMESPACE}}}tc"
TEXT_TAG = f"{{{WORD_NAMESPACE}}}t"
TAB_TAG = f"{{{WORD_NAMESPACE}}}tab"
BREAK_TAG = f"{{{WORD_NAMESPACE}}}br"


class DocxExtractionError(ValueError):
    pass


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for element in paragraph.iter():
        if element.tag == TEXT_TAG and element.text:
            parts.append(element.text)
        elif element.tag == TAB_TAG:
            parts.append("\t")
        elif element.tag == BREAK_TAG:
            parts.append("\n")
    return "".join(parts).strip()


def _document_blocks(element: ElementTree.Element) -> Iterator[ElementTree.Element]:
    """Yield paragraphs and tables in the order in which Word displays them."""
    for child in element:
        if child.tag in {PARAGRAPH_TAG, TABLE_TAG}:
            yield child
        else:
            # Content controls and similar containers can wrap regular document blocks.
            yield from _document_blocks(child)


def _cell_text(cell: ElementTree.Element) -> tuple[str, int]:
    paragraphs = [
        text
        for paragraph in cell.iter(PARAGRAPH_TAG)
        if (text := _paragraph_text(paragraph))
    ]
    return "\n".join(paragraphs), len(paragraphs)


def _markdown_cell(value: str) -> str:
    return (
        value.replace("|", "\\|")
        .replace("\r", "")
        .replace("\n", "<br>")
    )


def _table_markdown(table: ElementTree.Element, table_number: int) -> tuple[str, int]:
    rows: list[list[str]] = []
    paragraph_count = 0
    for row in table.findall(ROW_TAG):
        values: list[str] = []
        for cell in row.findall(CELL_TAG):
            value, cell_paragraph_count = _cell_text(cell)
            values.append(value)
            paragraph_count += cell_paragraph_count
        if any(value.strip() for value in values):
            rows.append(values)

    if not rows:
        return "", paragraph_count

    column_count = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]
    header = normalized_rows[0]
    if not any(value.strip() for value in header):
        header = [f"Cột {index + 1}" for index in range(column_count)]

    lines = [
        f"### Bảng {table_number}",
        "",
        f"| {' | '.join(_markdown_cell(value) for value in header)} |",
        f"| {' | '.join('---' for _ in range(column_count))} |",
    ]
    for row in normalized_rows[1:]:
        lines.append(f"| {' | '.join(_markdown_cell(value) for value in row)} |")
    return "\n".join(lines), paragraph_count


def extract_docx_text(
    payload: bytes,
    *,
    max_uncompressed_bytes: int,
    max_characters: int,
) -> tuple[str, int, int]:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            total_size = sum(item.file_size for item in archive.infolist())
            if total_size > max_uncompressed_bytes:
                raise DocxExtractionError("File DOCX sau khi giải nén vượt quá giới hạn cho phép.")
            try:
                document_xml = archive.read("word/document.xml")
            except KeyError as exc:
                raise DocxExtractionError("File không có cấu trúc DOCX hợp lệ.") from exc
    except BadZipFile as exc:
        raise DocxExtractionError("File không phải là tài liệu DOCX hợp lệ.") from exc

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        raise DocxExtractionError("Không thể đọc nội dung XML trong file DOCX.") from exc

    body = root.find(BODY_TAG)
    if body is None:
        raise DocxExtractionError("File không có phần nội dung DOCX hợp lệ.")

    blocks: list[str] = []
    paragraph_count = 0
    table_count = 0
    for block in _document_blocks(body):
        if block.tag == PARAGRAPH_TAG:
            text = _paragraph_text(block)
            if text:
                blocks.append(text)
                paragraph_count += 1
            continue

        table_count += 1
        table_text, table_paragraph_count = _table_markdown(block, table_count)
        paragraph_count += table_paragraph_count
        if table_text:
            blocks.append(table_text)

    content = "\n\n".join(blocks).strip()
    if not content:
        raise DocxExtractionError("File DOCX không chứa văn bản để chấm.")
    if len(content) > max_characters:
        raise DocxExtractionError(
            f"Văn bản sau khi trích xuất vượt quá {max_characters:,} ký tự."
        )
    return content, paragraph_count, table_count
