from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.pdf_loader_dto import PdfDocumentDetail, PdfDocumentSummary


class PdfDocumentRepository(ABC):
    """요약된 PDF 문서 영속 포트 — admin 자체 소유 테이블(admin_pdf_documents)."""

    @abstractmethod
    async def save(
        self, filename: str, title: str, text: str, summary: str
    ) -> PdfDocumentSummary:
        """추출 원문 + 요약을 저장하고, 부여된 id를 포함한 메타를 반환한다."""
        ...

    @abstractmethod
    async def list_recent(self, limit: int) -> list[PdfDocumentSummary]:
        """최근 문서를 최신순으로 반환한다(원문 제외)."""
        ...

    @abstractmethod
    async def find(self, document_id: int) -> PdfDocumentDetail | None:
        """문서 1건(원문 포함)을 반환한다. 없으면 None."""
        ...
