from stock.app.dtos.news_search_dto import NewsSearchRow
from stock.app.use_cases.news_interactor import NewsInteractor
from stock.domain.entities.news_article import NewsArticle


class _StubRepository:
    def __init__(self, pending: list[tuple[int, str]] | None = None):
        self.pending = pending or []
        self.saved: list[NewsArticle] = []
        self.embeddings: list[tuple[int, list[float]]] = []
        self.search_args: tuple | None = None

    async def save_many(self, articles):
        self.saved.extend(articles)
        return len(articles)

    async def recent_titles(self, query, ticker="", limit=5):
        return []

    async def unembedded(self, limit=200):
        return self.pending[:limit]

    async def set_embeddings(self, items):
        self.embeddings.extend(items)
        return len(items)

    async def search_similar(self, embedding, ticker=None, limit=5):
        self.search_args = (embedding, ticker, limit)
        return [NewsSearchRow(id=1, title="히트", ticker="NVDA", source="t",
                              published_at=None, sentiment=0.5, event_type="실적")]


class _StubEmbeddings:
    def __init__(self, fail: bool = False):
        self.fail = fail

    async def embed(self, text):
        if self.fail:
            raise RuntimeError("Ollama down")
        return [0.1] * 4

    async def embed_many(self, texts):
        if self.fail:
            raise RuntimeError("Ollama down")
        return [[0.1] * 4 for _ in texts]


def _article() -> NewsArticle:
    return NewsArticle(title="제목", source="t", url="https://a", ticker="NVDA")


async def test_적재_후_미임베딩분을_배치_임베딩한다():
    repo = _StubRepository(pending=[(1, "제목1"), (2, "제목2")])
    saved = await NewsInteractor(news=repo, embeddings=_StubEmbeddings()).ingest([_article()])
    assert saved == 1
    assert [row_id for row_id, _ in repo.embeddings] == [1, 2]


async def test_임베딩_실패해도_적재는_성공하고_NULL_유지():
    repo = _StubRepository(pending=[(1, "제목1")])
    saved = await NewsInteractor(news=repo, embeddings=_StubEmbeddings(fail=True)).ingest([_article()])
    assert saved == 1  # 수집 우선 — 예외 전파 없음
    assert repo.embeddings == []  # NULL 유지 → 다음 주기 재시도


async def test_임베딩_포트가_없으면_적재만_한다():
    repo = _StubRepository(pending=[(1, "제목1")])
    saved = await NewsInteractor(news=repo).ingest([_article()])
    assert saved == 1
    assert repo.embeddings == []


async def test_검색은_질의를_임베딩해_리포지토리에_위임한다():
    repo = _StubRepository()
    rows = await NewsInteractor(news=repo, embeddings=_StubEmbeddings()).search(
        "반도체 업황", ticker="NVDA", limit=3,
    )
    assert repo.search_args == ([0.1] * 4, "NVDA", 3)
    assert rows[0].title == "히트"


async def test_질의_임베딩_실패면_빈_결과():
    repo = _StubRepository()
    rows = await NewsInteractor(news=repo, embeddings=_StubEmbeddings(fail=True)).search("질의")
    assert rows == [] and repo.search_args is None

# --- B2 영향 키워드 ---


class _KeywordOnlyRepo:
    """top_keywords 경로가 쓰는 메서드만 — 표본을 그대로 돌려준다."""

    def __init__(self, rows):
        self.rows = rows
        self.calls: list[str] = []

    async def recent_labeled_titles(self, ticker, days=90, limit=100):
        self.calls.append(ticker)
        return self.rows


async def test_top_keywords는_최근_헤드라인_표본으로_결정론_추출한다():
    from datetime import datetime, timezone

    from stock.app.use_cases.news_interactor import NewsInteractor

    d = datetime(2026, 8, 22, tzinfo=timezone.utc)
    repo = _KeywordOnlyRepo([
        ("HBM 수주 확대", 0.5, d),
        ("HBM 공급 계약", 0.3, d),
        ("HBM 증설 검토", None, d),
        ("배당 확대 검토", 0.1, d),
        ("신제품 공개", None, d),
    ])
    got = await NewsInteractor(news=repo).top_keywords("005930.KS")
    assert repo.calls == ["005930.KS"]
    assert got[0].keyword == "hbm" and got[0].count == 3


async def test_top_keywords_표본_미달이면_빈_리스트():
    from stock.app.use_cases.news_interactor import NewsInteractor

    got = await NewsInteractor(news=_KeywordOnlyRepo([])).top_keywords("AAPL")
    assert got == []
