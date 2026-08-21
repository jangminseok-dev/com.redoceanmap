from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.fundamental_snapshot_orm import FundamentalSnapshotOrm
from stock.adapter.outbound.orm.news_article_orm import NewsArticleOrm
from stock.adapter.outbound.orm.news_label_orm import NewsLabelOrm
from stock.adapter.outbound.orm.price_bar_orm import PriceBarOrm
from stock.adapter.outbound.pg.news_pg_repository import DEFAULT_LABELER
from stock.app.dtos.stock_history_dto import StockNewsItem
from stock.app.ports.output.stock_history_repository import StockHistoryRepositoryPort
from stock.domain.entities.fundamental_snapshot import FundamentalSnapshot
from stock.domain.entities.price_bar import PriceBar


def _ticker_match(column, symbol: str):
    """거래소 접미 규칙(005930 ↔ 005930.KS) — news_pg_repository와 동일."""
    return or_(column == symbol, column.like(f"{symbol}.%"))


class StockHistoryPgRepository(StockHistoryRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_bars(self, symbol: str, timeframe: str, limit: int) -> list[PriceBar]:
        # 1단계: 접미 후보 중 실제 저장된 티커 하나를 확정한다(.KS/.KQ 혼입 방지)
        ticker = (await self._session.execute(
            select(PriceBarOrm.ticker)
            .where(_ticker_match(PriceBarOrm.ticker, symbol), PriceBarOrm.timeframe == timeframe)
            .order_by(PriceBarOrm.ts.desc())
            .limit(1)
        )).scalar()
        if ticker is None:
            return []

        rows = (await self._session.execute(
            select(PriceBarOrm)
            .where(PriceBarOrm.ticker == ticker, PriceBarOrm.timeframe == timeframe)
            .order_by(PriceBarOrm.ts.desc())
            .limit(limit)
        )).scalars().all()
        return [
            PriceBar(
                ticker=r.ticker, timeframe=r.timeframe, ts=r.ts,
                open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume,
            )
            for r in reversed(rows)  # 최신 limit개 → ts 오름차순
        ]

    async def find_news(self, symbol: str, limit: int) -> list[StockNewsItem]:
        stmt = (
            select(
                NewsArticleOrm,
                NewsLabelOrm.sentiment,
                NewsLabelOrm.event_type,
                NewsLabelOrm.confidence,
            )
            .outerjoin(NewsLabelOrm, and_(
                NewsLabelOrm.news_id == NewsArticleOrm.id,
                NewsLabelOrm.labeler == DEFAULT_LABELER,
            ))
            .where(_ticker_match(NewsArticleOrm.ticker, symbol))
            .order_by(NewsArticleOrm.published_at.desc().nulls_last(), NewsArticleOrm.id.desc())
            .limit(limit * 2)  # (url, ticker) 유니크 구조상 동일 제목 다행 — 여유 조회 후 dedupe
        )
        result = await self._session.execute(stmt)
        items: list[StockNewsItem] = []
        seen_titles: set[str] = set()
        for orm, sentiment, event_type, confidence in result.all():
            if orm.title in seen_titles:
                continue
            seen_titles.add(orm.title)
            items.append(StockNewsItem(
                id=orm.id, title=orm.title, source=orm.source, url=orm.url,
                published_at=orm.published_at,
                sentiment=sentiment, event_type=event_type, confidence=confidence,
            ))
            if len(items) >= limit:
                break
        return items

    async def find_latest_fundamentals(self, symbol: str) -> list[FundamentalSnapshot]:
        rows = (await self._session.execute(
            select(FundamentalSnapshotOrm)
            .where(
                _ticker_match(FundamentalSnapshotOrm.ticker, symbol),
                # yf-hist는 백테스트용 과거 백필 — "지금" 스냅샷이 아니라 화면·채팅에서 제외
                FundamentalSnapshotOrm.source != "yf-hist",
            )
            .order_by(FundamentalSnapshotOrm.as_of.desc())
            .limit(20)  # 주간 스냅샷 — 소스별 최신만 남기는 python dedupe에 충분한 창
        )).scalars().all()
        latest_by_source: dict[str, FundamentalSnapshotOrm] = {}
        for r in rows:
            latest_by_source.setdefault(r.source, r)
        return [
            FundamentalSnapshot(
                ticker=r.ticker, as_of=r.as_of, source=r.source,
                per=r.per, pbr=r.pbr, roe=r.roe, debt_to_equity=r.debt_to_equity,
                fcf=r.fcf, market_cap=r.market_cap, eps=r.eps, bps=r.bps,
            )
            for r in sorted(latest_by_source.values(), key=lambda r: r.source)
        ]
