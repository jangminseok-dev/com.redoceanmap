from __future__ import annotations

from hub.app.dtos.news_dto import NewsHit, NewsKeyword
from hub.app.ports.output.news_search_port import NewsSearchPort
from stock.app.ports.input.news_use_case import NewsIngestUseCase


class NewsSearchGateway(NewsSearchPort):
    """허브 NewsSearchPort 구현 — 의미 검색을 stock 유스케이스에 위임하고 허브 DTO로 변환."""

    def __init__(self, use_case: NewsIngestUseCase) -> None:
        self._use_case = use_case

    async def search(self, query: str, ticker: str | None = None, limit: int = 5) -> list[NewsHit]:
        return [
            NewsHit(
                title=row.title, ticker=row.ticker, published_at=row.published_at,
                sentiment=row.sentiment, event_type=row.event_type, source=row.source,
            )
            for row in await self._use_case.search(query, ticker=ticker, limit=limit)
        ]

    async def top_keywords(self, ticker: str, limit: int = 5) -> list[NewsKeyword]:
        return [
            NewsKeyword(
                keyword=k.keyword, count=k.count,
                sentiment_avg=k.sentiment_avg, sample_title=k.sample_title,
            )
            for k in await self._use_case.top_keywords(ticker, limit=limit)
        ]
