from __future__ import annotations

from abc import ABC, abstractmethod

from stock.app.dtos.news_search_dto import NewsSearchRow
from stock.domain.entities.news_article import NewsArticle
from stock.domain.services.keyword_extractor import KeywordInsight


class NewsIngestUseCase(ABC):
    """n8n 등 수집기가 보낸 뉴스를 적재하고, 의미 검색을 제공하는 인바운드 유스케이스."""

    @abstractmethod
    async def ingest(self, articles: list[NewsArticle]) -> int:
        """저장된 신규 건수를 반환한다."""
        ...

    @abstractmethod
    async def embed_pending(self, limit: int = 200) -> int:
        """미임베딩 뉴스를 배치 임베딩하고 처리 건수를 반환한다(백필·재시도)."""
        ...

    @abstractmethod
    async def search(
        self, query: str, ticker: str | None = None, limit: int = 5,
    ) -> list[NewsSearchRow]:
        """자연어 질의로 의미 검색한다. 임베딩 불가 시 빈 결과."""
        ...

    @abstractmethod
    async def top_keywords(self, ticker: str, limit: int = 5) -> list[KeywordInsight]:
        """종목 최근 헤드라인의 영향 키워드 Top-N(B2, 결정론). 표본 미달이면 빈 리스트."""
        ...
