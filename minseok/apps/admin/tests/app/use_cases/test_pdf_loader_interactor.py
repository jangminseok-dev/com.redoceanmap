from datetime import datetime, timezone

import pytest

from admin.app.dtos.pdf_loader_dto import (
    PdfDetailQuery,
    PdfDocumentDetail,
    PdfDocumentSummary,
    PdfListQuery,
    PdfUploadCommand,
)
from admin.app.exceptions import PdfDocumentNotFoundError, PdfTextEmptyError
from admin.app.use_cases.pdf_loader_interactor import PdfLoaderInteractor

_TEXT = "2025년 6월호 인공지능 산업의 최신 동향\nSPRi AI Brief\nEU 집행위원회 피드백 분석 결과 발표"


class _StubExtractor:
    def __init__(self, text=_TEXT):
        self.text = text
        self.received = None

    async def extract(self, filename, content):
        self.received = (filename, content)
        return self.text


class _StubSummarizer:
    def __init__(self):
        self.received = None

    async def summarize(self, title, text):
        self.received = (title, text)
        return "요약문"


class _StubRepository:
    def __init__(self, stored=None):
        self.saved = None
        self.requested_limit = None
        self._stored = stored

    async def save(self, filename, title, text, summary):
        self.saved = dict(filename=filename, title=title, text=text, summary=summary)
        return PdfDocumentSummary(
            id=7,
            filename=filename,
            title=title,
            summary=summary,
            char_count=len(text),
            created_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )

    async def list_recent(self, limit):
        self.requested_limit = limit
        return []

    async def find(self, document_id):
        return self._stored


class _StubAudit:
    def __init__(self):
        self.written = None

    async def write(self, actor_id, action, detail):
        self.written = (actor_id, action, detail)

    async def list_recent(self, limit):
        raise NotImplementedError


def _build(extractor=None, repository=None, audit=None):
    return PdfLoaderInteractor(
        extractor=extractor or _StubExtractor(),
        summarizer=_StubSummarizer(),
        repository=repository or _StubRepository(),
        audit=audit or _StubAudit(),
    )


async def test_업로드는_추출_요약_저장_감사_순으로_수행된다():
    extractor, repository, audit = _StubExtractor(), _StubRepository(), _StubAudit()
    interactor = _build(extractor=extractor, repository=repository, audit=audit)

    result = await interactor.summarize_upload(
        PdfUploadCommand(actor_id=3, filename="brief.pdf", content=b"%PDF-1.7")
    )

    assert extractor.received == ("brief.pdf", b"%PDF-1.7")
    assert repository.saved["text"] == _TEXT
    assert repository.saved["summary"] == "요약문"
    assert result.id == 7 and result.char_count == len(_TEXT)
    actor_id, action, detail = audit.written
    assert (actor_id, action) == (3, "pdf.summarize")
    assert "document=7" in detail


async def test_제목은_첫_유효줄에서_뽑는다():
    repository = _StubRepository()
    await _build(repository=repository).summarize_upload(
        PdfUploadCommand(actor_id=1, filename="brief.pdf", content=b"x")
    )
    assert repository.saved["title"] == "2025년 6월호 인공지능 산업의 최신 동향"


async def test_텍스트_레이어가_없으면_거부하고_저장하지_않는다():
    repository, audit = _StubRepository(), _StubAudit()
    interactor = _build(extractor=_StubExtractor(text="   \n\n"), repository=repository, audit=audit)

    with pytest.raises(PdfTextEmptyError):
        await interactor.summarize_upload(
            PdfUploadCommand(actor_id=1, filename="scan.pdf", content=b"x")
        )
    assert repository.saved is None and audit.written is None


async def test_목록_limit은_상한으로_보정한다():
    repository = _StubRepository()
    await _build(repository=repository).list_documents(PdfListQuery(limit=99999))
    assert repository.requested_limit == 100


async def test_없는_문서_조회는_예외다():
    with pytest.raises(PdfDocumentNotFoundError):
        await _build().get_document(PdfDetailQuery(document_id=404))


async def test_상세는_원문을_함께_반환한다():
    stored = PdfDocumentDetail(
        document=PdfDocumentSummary(
            id=7,
            filename="brief.pdf",
            title="제목",
            summary="요약문",
            char_count=len(_TEXT),
            created_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        ),
        text=_TEXT,
    )
    result = await _build(repository=_StubRepository(stored=stored)).get_document(
        PdfDetailQuery(document_id=7)
    )
    assert result.text == _TEXT and result.document.id == 7
