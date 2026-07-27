from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from admin.adapter.inbound.api.schemas.pdf_loader_schema import (
    PdfDetailResponseSchema,
    PdfDocumentSchema,
    PdfListResponseSchema,
)
from admin.app.dtos.pdf_loader_dto import (
    PdfDetailQuery,
    PdfDocumentSummary,
    PdfListQuery,
    PdfUploadCommand,
)
from admin.app.exceptions import (
    PdfDocumentNotFoundError,
    PdfExtractionError,
    PdfTextEmptyError,
)
from admin.app.ports.input.pdf_loader_use_case import PdfLoaderUseCase
from admin.dependencies.pdf_loader_provider import get_pdf_loader_use_case
from core.security import require_permission

pdf_loader_router = APIRouter(prefix="/admin", tags=["admin"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB — 어드민 수동 업로드 전제


def _to_schema(d: PdfDocumentSummary) -> PdfDocumentSchema:
    return PdfDocumentSchema(
        id=d.id,
        filename=d.filename,
        title=d.title,
        summary=d.summary,
        charCount=d.char_count,
        createdAt=d.created_at,
    )


@pdf_loader_router.post(
    "/pdf-documents",
    response_model=PdfDocumentSchema,
    status_code=201,
    summary="PDF 업로드 → 텍스트 추출 → 요약 저장",
)
async def upload_pdf(
    file: UploadFile = File(...),
    actor_id: int = Depends(require_permission("documents:write")),
    use_case: PdfLoaderUseCase = Depends(get_pdf_loader_use_case),
) -> PdfDocumentSchema:
    filename = file.filename or "unnamed.pdf"
    is_pdf = (file.content_type or "").lower() == "application/pdf" or filename.lower().endswith(
        ".pdf"
    )
    if not is_pdf:
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"파일이 너무 큽니다(최대 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB)."
        )

    try:
        document = await use_case.summarize_upload(
            PdfUploadCommand(actor_id=actor_id, filename=filename, content=content)
        )
    except (PdfExtractionError, PdfTextEmptyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_schema(document)


@pdf_loader_router.get(
    "/pdf-documents",
    response_model=PdfListResponseSchema,
    dependencies=[Depends(require_permission("documents:read"))],
)
async def list_pdf_documents(
    limit: int = 20,
    use_case: PdfLoaderUseCase = Depends(get_pdf_loader_use_case),
) -> PdfListResponseSchema:
    result = await use_case.list_documents(PdfListQuery(limit=limit))
    return PdfListResponseSchema(items=[_to_schema(d) for d in result.items])


@pdf_loader_router.get(
    "/pdf-documents/{document_id}",
    response_model=PdfDetailResponseSchema,
    dependencies=[Depends(require_permission("documents:read"))],
)
async def get_pdf_document(
    document_id: int,
    use_case: PdfLoaderUseCase = Depends(get_pdf_loader_use_case),
) -> PdfDetailResponseSchema:
    try:
        detail = await use_case.get_document(PdfDetailQuery(document_id=document_id))
    except PdfDocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PdfDetailResponseSchema(document=_to_schema(detail.document), text=detail.text)
