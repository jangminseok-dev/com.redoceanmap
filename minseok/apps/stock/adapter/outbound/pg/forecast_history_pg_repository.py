from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.price_bar_orm import PriceBarOrm
from stock.app.ports.output.forecast_history_port import ForecastHistoryPort
from stock.domain.entities.price_bar import PriceBar


class ForecastHistoryPgRepository(ForecastHistoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_latest_daily_bar(self, symbol: str) -> PriceBar | None:
        r = (await self._session.execute(
            select(PriceBarOrm)
            .where(
                or_(PriceBarOrm.ticker == symbol, PriceBarOrm.ticker.like(f"{symbol}.%")),
                PriceBarOrm.timeframe == "1d",
            )
            .order_by(PriceBarOrm.ts.desc())
            .limit(1)
        )).scalar()
        if r is None:
            return None
        return PriceBar(
            ticker=r.ticker, timeframe=r.timeframe, ts=r.ts,
            open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume,
        )

    async def _resolve_ticker(self, symbol: str) -> str | None:
        # 접미 후보 중 실제 저장된 티커를 확정(stock_history와 동일 규칙: 005930 ↔ 005930.KS)
        return (await self._session.execute(
            select(PriceBarOrm.ticker)
            .where(
                or_(PriceBarOrm.ticker == symbol, PriceBarOrm.ticker.like(f"{symbol}.%")),
                PriceBarOrm.timeframe == "1d",
            )
            .order_by(PriceBarOrm.ts.desc())
            .limit(1)
        )).scalar()

    @staticmethod
    def _to_bars(rows) -> list[PriceBar]:
        return [
            PriceBar(
                ticker=r.ticker, timeframe=r.timeframe, ts=r.ts,
                open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume,
            )
            for r in rows
        ]

    async def find_all_daily_bars(self, symbol: str) -> list[PriceBar]:
        ticker = await self._resolve_ticker(symbol)
        if ticker is None:
            return []
        rows = (await self._session.execute(
            select(PriceBarOrm)
            .where(PriceBarOrm.ticker == ticker, PriceBarOrm.timeframe == "1d")
            .order_by(PriceBarOrm.ts.asc())
        )).scalars().all()
        return self._to_bars(rows)

    async def find_recent_daily_bars(self, symbol: str, limit: int) -> list[PriceBar]:
        ticker = await self._resolve_ticker(symbol)
        if ticker is None:
            return []
        rows = (await self._session.execute(
            select(PriceBarOrm)
            .where(PriceBarOrm.ticker == ticker, PriceBarOrm.timeframe == "1d")
            .order_by(PriceBarOrm.ts.desc())
            .limit(limit)
        )).scalars().all()
        return self._to_bars(reversed(rows))
