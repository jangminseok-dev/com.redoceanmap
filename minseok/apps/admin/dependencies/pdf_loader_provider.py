from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from admin.adapter.outbound.exaone_pdf_summarizer_adapter import ExaonePdfSummarizerAdapter
from admin.adapter.outbound.pdf_loader_extractor_adapter import PdfLoaderExtractorAdapter
from admin.adapter.outbound.pg.audit_log_pg_adapter import AuditLogPgAdapter
from admin.adapter.outbound.pg.pdf_document_pg_adapter import PdfDocumentPgAdapter
from admin.app.ports.input.pdf_loader_use_case import PdfLoaderUseCase
from admin.app.ports.output.audit_log_port import AuditLogPort
from admin.app.ports.output.pdf_document_repository import PdfDocumentRepository
from admin.app.ports.output.pdf_summarizer_port import PdfSummarizerPort
from admin.app.ports.output.pdf_text_extractor_port import PdfTextExtractorPort
from admin.app.use_cases.pdf_loader_interactor import PdfLoaderInteractor
from core.database import get_db

# 추출기·요약기는 무상태라 프로세스당 1개면 충분하다(세션 의존 없음).
_extractor = PdfLoaderExtractorAdapter()
_summarizer = ExaonePdfSummarizerAdapter()


def get_pdf_text_extractor_port() -> PdfTextExtractorPort:
    return _extractor


def get_pdf_summarizer_port() -> PdfSummarizerPort:
    return _summarizer


def get_pdf_document_repository(db: AsyncSession = Depends(get_db)) -> PdfDocumentRepository:
    return PdfDocumentPgAdapter(session=db)


def get_pdf_audit_log_port(db: AsyncSession = Depends(get_db)) -> AuditLogPort:
    return AuditLogPgAdapter(session=db)


def get_pdf_loader_use_case(
    extractor: PdfTextExtractorPort = Depends(get_pdf_text_extractor_port),
    summarizer: PdfSummarizerPort = Depends(get_pdf_summarizer_port),
    repository: PdfDocumentRepository = Depends(get_pdf_document_repository),
    audit: AuditLogPort = Depends(get_pdf_audit_log_port),
) -> PdfLoaderUseCase:
    return PdfLoaderInteractor(
        extractor=extractor, summarizer=summarizer, repository=repository, audit=audit
    )
