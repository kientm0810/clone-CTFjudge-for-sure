from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import get_settings
from app.schemas.documents import DocumentExtraction
from app.services.docx_service import DocxExtractionError, extract_docx_text


router = APIRouter(prefix="/documents", tags=["documents"])
DocxFile = Annotated[UploadFile, File(description="Tài liệu Microsoft Word .docx")]


@router.post("/extract-docx", response_model=DocumentExtraction)
async def extract_docx(file: DocxFile) -> DocumentExtraction:
    settings = get_settings()
    filename = (file.filename or "document.docx").strip()
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=415, detail="Chỉ hỗ trợ file có đuôi .docx.")

    payload = await file.read(settings.max_docx_upload_bytes + 1)
    await file.close()
    if len(payload) > settings.max_docx_upload_bytes:
        limit_mb = settings.max_docx_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File DOCX không được lớn hơn {limit_mb} MB.",
        )
    if not payload.startswith(b"PK"):
        raise HTTPException(status_code=415, detail="Nội dung file không phải định dạng DOCX hợp lệ.")

    try:
        content, paragraph_count, table_count = extract_docx_text(
            payload,
            max_uncompressed_bytes=settings.max_docx_uncompressed_bytes,
            max_characters=settings.max_extracted_text_chars,
        )
    except DocxExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DocumentExtraction(
        filename=filename,
        content=content,
        character_count=len(content),
        paragraph_count=paragraph_count,
        table_count=table_count,
    )
