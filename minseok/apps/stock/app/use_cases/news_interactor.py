from __future__ import annotations

import logging

from stock.app.dtos.news_search_dto import NewsSearchRow
from stock.app.ports.input.news_use_case import NewsIngestUseCase
from stock.app.ports.output.embedding_port import EmbeddingPort
from stock.app.ports.output.news_repository import NewsRepositoryPort
from stock.domain.entities.news_article import NewsArticle
from stock.domain.services.keyword_extractor import (
    HeadlineSample,
    KeywordInsight,
    extract_keywords,
)

logger = logging.getLogger(__name__)

EMBED_BATCH_LIMIT = 200  # 주기당 임베딩 상한 — CPU 전용 Ollama면 50 수준으로 낮춘다


class NewsInteractor(NewsIngestUseCase):
    """뉴스 적재·검색 대장. 저장(중복 무시) 후 미임베딩분을 배치 임베딩한다."""

    def __init__(self, news: NewsRepositoryPort, embeddings: EmbeddingPort | None = None) -> None:
        self._news = news
        self._embeddings = embeddings

    async def ingest(self, articles: list[NewsArticle]) -> int:
        saved = await self._news.save_many(articles)
        # 신규분 + 과거 백로그(임베딩 실패분)를 30분 수집 주기마다 자연 소화 — 별도 백필 불요
        embedded = await self.embed_pending()
        logger.info("[stock-news] 수신 %d건 중 신규 %d건 저장 / 임베딩 %d건", len(articles), saved, embedded)
        return saved

    async def embed_pending(self, limit: int = EMBED_BATCH_LIMIT) -> int:
        """미임베딩 행을 배치 임베딩. 실패 시 NULL 유지 — 다음 주기 재시도(수집 우선)."""
        if self._embeddings is None:
            return 0
        rows = await self._news.unembedded(limit)
        if not rows:
            return 0
        try:
            vectors = await self._embeddings.embed_many([title for _, title in rows])
        except Exception:
            logger.warning("[stock-news] 임베딩 실패 — NULL 유지, 다음 주기 재시도", exc_info=True)
            return 0
        return await self._news.set_embeddings(
            [(row_id, vector) for (row_id, _), vector in zip(rows, vectors)]
        )

    async def search(
        self, query: str, ticker: str | None = None, limit: int = 5,
    ) -> list[NewsSearchRow]:
        """자연어 질의 의미 검색. 임베딩 불가 시 빈 결과(검색 열화 — 예외 전파 금지)."""
        if self._embeddings is None:
            return []
        try:
            embedding = await self._embeddings.embed(query)
        except Exception:
            logger.warning("[stock-news] 질의 임베딩 실패 — 빈 결과 반환", exc_info=True)
            return []
        return await self._news.search_similar(embedding, ticker=ticker, limit=limit)

    async def top_keywords(self, ticker: str, limit: int = 5) -> list[KeywordInsight]:
        """최근 헤드라인 표본 → 결정론 키워드 추출(B2). 임베딩과 무관해 항상 동작한다."""
        rows = await self._news.recent_labeled_titles(ticker)
        samples = [
            HeadlineSample(title=title, sentiment=sentiment, published_at=published_at)
            for title, sentiment, published_at in rows
        ]
        return extract_keywords(samples, limit=limit)
