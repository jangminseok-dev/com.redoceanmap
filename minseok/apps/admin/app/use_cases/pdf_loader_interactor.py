from __future__ import annotations

from admin.app.dtos.pdf_loader_dto import (
    PdfDetailQuery,
    PdfDocumentDetail,
    PdfDocumentSummary,
    PdfListQuery,
    PdfListResponse,
    PdfUploadCommand,
)
from admin.app.exceptions import PdfDocumentNotFoundError, PdfTextEmptyError
from admin.app.ports.input.pdf_loader_use_case import PdfLoaderUseCase
from admin.app.ports.output.audit_log_port import AuditLogPort
from admin.app.ports.output.pdf_document_repository import PdfDocumentRepository
from admin.app.ports.output.pdf_summarizer_port import PdfSummarizerPort
from admin.app.ports.output.pdf_text_extractor_port import PdfTextExtractorPort

MAX_LIMIT = 100
TITLE_MAX_CHARS = 200


def _derive_title(text: str, filename: str) -> str:
    """첫 유효 줄을 제목으로 삼고, 없으면 파일명으로 대체한다."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:TITLE_MAX_CHARS]
    return filename[:TITLE_MAX_CHARS]


class PdfLoaderInteractor(PdfLoaderUseCase):
    """PDF 요약 파이프라인 대장 — 추출 → 요약 → 영속 → 감사 기록 순으로 포트를 조립한다.

    각 단계는 전부 아웃바운드 포트다(pypdf도 Ollama도 이 계층에서는 보이지 않는다).
    감사는 admin 규칙대로 '변경 행위'인 업로드에만 남기고 조회에는 남기지 않는다.
    """

    def __init__(
        self,
        extractor: PdfTextExtractorPort,
        summarizer: PdfSummarizerPort,
        repository: PdfDocumentRepository,
        audit: AuditLogPort,
    ) -> None:
        self._extractor = extractor
        self._summarizer = summarizer
        self._repository = repository
        self._audit = audit

    async def summarize_upload(self, command: PdfUploadCommand) -> PdfDocumentSummary:
        text = (await self._extractor.extract(command.filename, command.content)).strip()
        if not text:
            raise PdfTextEmptyError(
                "PDF에서 추출된 텍스트가 없습니다(스캔 이미지 PDF일 수 있습니다)."
            )

        title = _derive_title(text, command.filename)
        summary = await self._summarizer.summarize(title, text)
        document = await self._repository.save(
            filename=command.filename, title=title, text=text, summary=summary
        )
        await self._audit.write(
            actor_id=command.actor_id,
            action="pdf.summarize",
            detail=f"document={document.id} file={command.filename} chars={document.char_count}",
        )
        return document

    async def list_documents(self, query: PdfListQuery) -> PdfListResponse:
        limit = min(max(query.limit, 1), MAX_LIMIT)
        return PdfListResponse(items=await self._repository.list_recent(limit))

    async def get_document(self, query: PdfDetailQuery) -> PdfDocumentDetail:
        found = await self._repository.find(query.document_id)
        if found is None:
            raise PdfDocumentNotFoundError(f"문서를 찾을 수 없습니다: id={query.document_id}")
        return found
