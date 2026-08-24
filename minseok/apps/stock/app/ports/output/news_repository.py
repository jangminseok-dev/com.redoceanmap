from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from stock.app.dtos.news_search_dto import NewsSearchRow
from stock.domain.entities.news_article import NewsArticle


class NewsRepositoryPort(ABC):
    """수집 뉴스 저장/조회 아웃바운드 포트. 구현(PG 등)은 어댑터가 제공."""

    @abstractmethod
    async def save_many(self, articles: list[NewsArticle]) -> int:
        """저장하고 신규 건수를 반환한다. (url, ticker) 중복은 무시한다."""
        ...

    @abstractmethod
    async def recent_titles(self, query: str, ticker: str = "", limit: int = 5) -> list[str]:
        """ticker 일치 또는 제목에 query가 포함된 최신 뉴스 제목을 반환한다."""
        ...

    @abstractmethod
    async def unembedded(self, limit: int = 200) -> list[tuple[int, str]]:
        """임베딩이 없는 (id, title)을 최신순으로 반환한다."""
        ...

    @abstractmethod
    async def set_embeddings(self, items: list[tuple[int, list[float]]]) -> int:
        """id별 임베딩을 저장하고 건수를 반환한다."""
        ...

    @abstractmethod
    async def search_similar(
        self, embedding: list[float], ticker: str | None = None, limit: int = 5,
    ) -> list[NewsSearchRow]:
        """코사인 유사도 상위 뉴스를 라벨(감성·이벤트)과 함께 반환한다. ticker로 범위 제한 가능."""
        ...

    @abstractmethod
    async def recent_labeled_titles(
        self, ticker: str, days: int = 90, limit: int = 100,
    ) -> list[tuple[str, float | None, datetime | None]]:
        """종목의 최근 헤드라인 (제목, 감성 라벨, 발행일) — 키워드 추출(B2)의 표본.

        접미 매칭(005930 ↔ 005930.KS)은 구현 몫. 제목 중복은 제거해 반환한다."""
        ...

    @abstractmethod
    async def sentiment_baseline(self, ticker: str, days: int = 30) -> tuple[float | None, int]:
        """종목의 최근 N일 뉴스 라벨 감성 (평균, 표본 수) — 감성 서프라이즈의 기준선.

        라벨(news_labels)이 없으면 (None, 0). 접미 매칭(005930 ↔ 005930.KS)은 구현 몫."""
        ...
