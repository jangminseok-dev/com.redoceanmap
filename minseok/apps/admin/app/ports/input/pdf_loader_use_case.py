from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.pdf_loader_dto import (
    PdfDetailQuery,
    PdfDocumentDetail,
    PdfDocumentSummary,
    PdfListQuery,
    PdfListResponse,
    PdfUploadCommand,
)


class PdfLoaderUseCase(ABC):
    """PDF 업로드 → 텍스트 추출 → 요약 → 영속 파이프라인 유스케이스."""

    @abstractmethod
    async def summarize_upload(self, command: PdfUploadCommand) -> PdfDocumentSummary:
        """업로드된 PDF의 텍스트를 추출·요약해 저장하고 메타를 반환한다."""
        ...

    @abstractmethod
    async def list_documents(self, query: PdfListQuery) -> PdfListResponse:
        """최근 요약 문서를 최신순으로 반환한다(원문 제외)."""
        ...

    @abstractmethod
    async def get_document(self, query: PdfDetailQuery) -> PdfDocumentDetail:
        """문서 1건의 메타 + 추출 원문을 반환한다."""
        ...
