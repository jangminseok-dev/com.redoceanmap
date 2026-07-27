from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PdfUploadCommand:
    """PDF 업로드 요약 요청 — 라우터가 UploadFile을 읽어 바이트로 넘긴다."""

    actor_id: int
    filename: str
    content: bytes


@dataclass(frozen=True)
class PdfDocumentSummary:
    """목록·응답용 메타 — 추출 원문은 담지 않는다(응답 비대화 방지)."""

    id: int
    filename: str
    title: str
    summary: str
    char_count: int
    created_at: datetime


@dataclass(frozen=True)
class PdfDocumentDetail:
    """상세 — 메타 + 추출 원문."""

    document: PdfDocumentSummary
    text: str


@dataclass(frozen=True)
class PdfListQuery:
    limit: int


@dataclass(frozen=True)
class PdfListResponse:
    items: list[PdfDocumentSummary]


@dataclass(frozen=True)
class PdfDetailQuery:
    document_id: int
