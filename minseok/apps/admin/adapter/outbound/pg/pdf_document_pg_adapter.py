from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.adapter.outbound.orm.pdf_document_orm import PdfDocumentOrm
from admin.app.dtos.pdf_loader_dto import PdfDocumentDetail, PdfDocumentSummary
from admin.app.ports.output.pdf_document_repository import PdfDocumentRepository


def _to_summary(row: PdfDocumentOrm) -> PdfDocumentSummary:
    return PdfDocumentSummary(
        id=row.id,
        filename=row.filename,
        title=row.title,
        summary=row.summary,
        char_count=row.char_count,
        created_at=row.created_at,
    )


class PdfDocumentPgAdapter(PdfDocumentRepository):
    """PdfDocumentRepository의 PG 구현 — admin_pdf_documents 테이블."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self, filename: str, title: str, text: str, summary: str
    ) -> PdfDocumentSummary:
        row = PdfDocumentOrm(
            filename=filename,
            title=title,
            extracted_text=text,
            summary=summary,
            char_count=len(text),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)  # id·created_at(server_default) 확정
        return _to_summary(row)

    async def list_recent(self, limit: int) -> list[PdfDocumentSummary]:
        rows = (
            await self._session.execute(
                select(PdfDocumentOrm).order_by(PdfDocumentOrm.id.desc()).limit(limit)
            )
        ).scalars().all()
        return [_to_summary(r) for r in rows]

    async def find(self, document_id: int) -> PdfDocumentDetail | None:
        row = await self._session.get(PdfDocumentOrm, document_id)
        if row is None:
            return None
        return PdfDocumentDetail(document=_to_summary(row), text=row.extracted_text)
