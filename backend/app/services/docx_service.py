from io import BytesIO
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PARAGRAPH_TAG = f"{{{WORD_NAMESPACE}}}p"
TEXT_TAG = f"{{{WORD_NAMESPACE}}}t"
TAB_TAG = f"{{{WORD_NAMESPACE}}}tab"
BREAK_TAG = f"{{{WORD_NAMESPACE}}}br"


class DocxExtractionError(ValueError):
    pass


def extract_docx_text(
    payload: bytes,
    *,
    max_uncompressed_bytes: int,
    max_characters: int,
) -> tuple[str, int]:
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

    paragraphs: list[str] = []
    for paragraph in root.iter(PARAGRAPH_TAG):
        parts: list[str] = []
        for element in paragraph.iter():
            if element.tag == TEXT_TAG and element.text:
                parts.append(element.text)
            elif element.tag == TAB_TAG:
                parts.append("\t")
            elif element.tag == BREAK_TAG:
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)

    content = "\n\n".join(paragraphs).strip()
    if not content:
        raise DocxExtractionError("File DOCX không chứa văn bản để chấm.")
    if len(content) > max_characters:
        raise DocxExtractionError(
            f"Văn bản sau khi trích xuất vượt quá {max_characters:,} ký tự."
        )
    return content, len(paragraphs)
