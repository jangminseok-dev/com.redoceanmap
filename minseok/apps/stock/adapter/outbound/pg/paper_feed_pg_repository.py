"""모의투자 피드 — 스냅샷·봉·뉴스를 as_of 이전으로만 읽는다(리플레이 정직성의 구현 지점)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.forecast_snapshot_orm import ForecastSnapshotOrm
from stock.adapter.outbound.orm.news_article_orm import NewsArticleOrm
from stock.adapter.outbound.orm.news_label_orm import NewsLabelOrm
from stock.adapter.outbound.orm.price_bar_orm import PriceBarOrm
from stock.adapter.outbound.pg.news_pg_repository import DEFAULT_LABELER
from stock.adapter.outbound.pg.stock_history_pg_repository import _ticker_match
from stock.app.dtos.paper_dto import NewsFeedRow, SnapshotFeedRow
from stock.app.ports.output.paper_feed_port import PaperFeedPort
from stock.domain.entities.price_bar import PriceBar


def _bar(r: PriceBarOrm) -> PriceBar:
    return PriceBar(ticker=r.ticker, timeframe=r.timeframe, ts=r.ts, open=r.open, high=r.high, low=r.low,
                    close=r.close, volume=r.volume)


class PaperFeedPgRepository(PaperFeedPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def snapshots_on(self, day: date, horizon: int) -> list[SnapshotFeedRow]:
        start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        rows = (await self._session.execute(
            select(ForecastSnapshotOrm).where(
                ForecastSnapshotOrm.horizon_days == horizon,
                ForecastSnapshotOrm.as_of >= start, ForecastSnapshotOrm.as_of < start + timedelta(days=1),
            ).distinct(ForecastSnapshotOrm.ticker).order_by(ForecastSnapshotOrm.ticker, ForecastSnapshotOrm.as_of.desc())
        )).scalars().all()
        return [SnapshotFeedRow(r.ticker, r.as_of, r.direction, r.score, r.base_price, r.up_rate, r.baseline_up_rate,
                                bool(r.ready), r.atr_pct, r.regime, bool(r.earnings_veto)) for r in rows]

    async def bars_after(self, ticker, after, until, limit):
        rows = (await self._session.execute(
            select(PriceBarOrm).where(_ticker_match(PriceBarOrm.ticker, ticker), PriceBarOrm.timeframe == "1d",
                                      PriceBarOrm.ts > after, PriceBarOrm.ts <= until)
            .order_by(PriceBarOrm.ts.asc()).limit(limit)
        )).scalars().all()
        return [_bar(r) for r in rows]

    async def bars_until(self, ticker, until, limit):
        rows = (await self._session.execute(
            select(PriceBarOrm).where(_ticker_match(PriceBarOrm.ticker, ticker), PriceBarOrm.timeframe == "1d",
                                      PriceBarOrm.ts <= until)
            .order_by(PriceBarOrm.ts.desc()).limit(limit)
        )).scalars().all()
        return [_bar(r) for r in reversed(rows)]

    async def latest_close(self, ticker):
        row = (await self._session.execute(
            select(PriceBarOrm).where(_ticker_match(PriceBarOrm.ticker, ticker))
            .order_by(PriceBarOrm.ts.desc()).limit(1)
        )).scalar_one_or_none()
        return (row.close, row.ts) if row else None

    async def news_between(self, ticker, since, until, limit):
        rows = (await self._session.execute(
            select(NewsArticleOrm, NewsLabelOrm.sentiment, NewsLabelOrm.event_type)
            .outerjoin(NewsLabelOrm, (NewsLabelOrm.news_id == NewsArticleOrm.id) & (NewsLabelOrm.labeler == DEFAULT_LABELER))
            .where(_ticker_match(NewsArticleOrm.ticker, ticker), NewsArticleOrm.published_at >= since,
                   NewsArticleOrm.published_at <= until)
            .order_by(NewsArticleOrm.published_at.desc()).limit(limit * 2)
        )).all()
        out, seen = [], set()
        for a, sentiment, event_type in rows:
            if a.title in seen:
                continue
            seen.add(a.title)
            out.append(NewsFeedRow(a.id, a.title, a.url, a.published_at, sentiment, event_type))
            if len(out) >= limit:
                break
        return out

    async def spy_closes(self, until):
        rows = (await self._session.execute(
            select(PriceBarOrm).where(PriceBarOrm.ticker == "SPY", PriceBarOrm.timeframe == "1d", PriceBarOrm.ts <= until)
            .order_by(PriceBarOrm.ts.asc())
        )).scalars().all()
        return [_bar(r) for r in rows]
