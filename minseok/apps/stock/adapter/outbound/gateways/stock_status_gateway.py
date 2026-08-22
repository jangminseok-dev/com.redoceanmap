from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.stock_status_dto import StockStatusInfo
from hub.app.ports.output.stock_status_port import StockStatusPort
from stock.adapter.outbound.orm.forecast_snapshot_orm import ForecastSnapshotOrm
from stock.adapter.outbound.orm.price_bar_orm import PriceBarOrm

# stock_board_pg_repository와 같은 기준 — 이보다 오래된 스냅샷은 최신인 척 내보내지 않는다.
STALE_AFTER_DAYS = 10
# 신호 지평 — 보드(stock_board)의 기본값과 동일.
HORIZON_DAYS = 5


class StockStatusGateway(StockStatusPort):
    """허브의 StockStatusPort를 stock(스포크)이 구현한다.

    동결 스냅샷(forecast_snapshots) + 최근 종가 2봉(price_bars)만 읽는다 —
    심볼마다 analyze를 부르면 벤더 호출이 심볼 수만큼 나는 것을 피한다(stock_board와 같은 이유).
    거래소 접미 변형(005930 ↔ 005930.KS)은 여기서 흡수한다(stock_history의 _ticker_match 규칙).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_statuses(self, symbols: list[str]) -> dict[str, StockStatusInfo]:
        if not symbols:
            return {}
        cutoff = datetime.now(UTC) - timedelta(days=STALE_AFTER_DAYS)
        match = or_(*[
            (ForecastSnapshotOrm.ticker == s) | ForecastSnapshotOrm.ticker.like(f"{s}.%")
            for s in symbols
        ])
        snapshots = (await self._session.execute(
            select(ForecastSnapshotOrm)
            .where(
                ForecastSnapshotOrm.horizon_days == HORIZON_DAYS,
                ForecastSnapshotOrm.as_of >= cutoff,
                match,
            )
            .distinct(ForecastSnapshotOrm.ticker)
            .order_by(ForecastSnapshotOrm.ticker, ForecastSnapshotOrm.as_of.desc())
        )).scalars().all()
        if not snapshots:
            return {}

        closes = await self._last_two_closes([s.ticker for s in snapshots])
        result: dict[str, StockStatusInfo] = {}
        for snap in snapshots:
            symbol = self._requested_symbol(snap.ticker, symbols)
            if symbol is None:
                continue
            recent = closes.get(snap.ticker, [])
            price = recent[-1][1] if recent else snap.base_price
            previous = recent[-2][1] if len(recent) >= 2 else None
            result[symbol] = StockStatusInfo(
                ticker=snap.ticker,
                as_of=snap.as_of,
                direction=snap.direction,
                price=price,
                change_pct=(price / previous - 1.0) if previous else None,
                up_rate=snap.up_rate,
                baseline_up_rate=snap.baseline_up_rate,
                ready=snap.ready,
                price_as_of=recent[-1][0] if recent else None,
            )
        return result

    @staticmethod
    def _requested_symbol(stored: str, symbols: list[str]) -> str | None:
        """저장 티커를 요청 심볼로 되돌린다 (005930.KS → 요청이 005930이면 005930)."""
        for s in symbols:
            if stored == s or stored.startswith(f"{s}."):
                return s
        return None

    async def _last_two_closes(
        self, tickers: list[str]
    ) -> dict[str, list[tuple[datetime, float]]]:
        """티커별 최근 일봉 2개 (ts 오름차순) — 최신 종가와 전일 대비 계산용."""
        ranked = (
            select(
                PriceBarOrm.ticker,
                PriceBarOrm.ts,
                PriceBarOrm.close,
                func.row_number()
                .over(partition_by=PriceBarOrm.ticker, order_by=PriceBarOrm.ts.desc())
                .label("rn"),
            )
            .where(PriceBarOrm.timeframe == "1d", PriceBarOrm.ticker.in_(tickers))
            .subquery()
        )
        rows = (await self._session.execute(
            select(ranked.c.ticker, ranked.c.ts, ranked.c.close)
            .where(ranked.c.rn <= 2)
            .order_by(ranked.c.ticker, ranked.c.ts.asc())
        )).all()
        out: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        for ticker, ts, close in rows:
            out[ticker].append((ts, float(close)))
        return out
