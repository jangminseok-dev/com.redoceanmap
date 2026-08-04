from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.forecast_snapshot_orm import ForecastSnapshotOrm
from stock.adapter.outbound.orm.price_bar_orm import PriceBarOrm
from stock.app.dtos.stock_board_dto import BoardSignalRow
from stock.app.ports.output.stock_board_repository import StockBoardRepositoryPort

# 이보다 오래된 스냅샷은 보드에서 뺀다 — 워치리스트에서 빠진 종목의 몇 달 전 판정이
# 최신인 척 상단에 남는 것을 막는다. 연휴+주말을 넘기도록 10일로 둔다.
STALE_AFTER_DAYS = 10


class StockBoardPgRepository(StockBoardRepositoryPort):
    """forecast_snapshots(티커별 최신) + price_bars(최근 종가) 두 번의 조회로 보드를 만든다.

    종목마다 analyze/forecast를 부르면 워치리스트 크기만큼 벤더 호출이 나므로,
    이미 일일 cron이 동결해 둔 스냅샷만 읽는다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_latest_signals(self, horizon: int, sparkline_bars: int) -> list[BoardSignalRow]:
        cutoff = datetime.now(UTC) - timedelta(days=STALE_AFTER_DAYS)
        snapshots = (await self._session.execute(
            select(ForecastSnapshotOrm)
            .where(
                ForecastSnapshotOrm.horizon_days == horizon,
                ForecastSnapshotOrm.as_of >= cutoff,
            )
            # DISTINCT ON (ticker) — 티커별 가장 최근 as_of 한 줄
            .distinct(ForecastSnapshotOrm.ticker)
            .order_by(ForecastSnapshotOrm.ticker, ForecastSnapshotOrm.as_of.desc())
        )).scalars().all()
        if not snapshots:
            return []

        closes, price_dates, volumes = await self._recent_closes(
            [s.ticker for s in snapshots], sparkline_bars
        )
        return [
            BoardSignalRow(
                ticker=s.ticker,
                as_of=s.as_of,
                direction=s.direction,
                score=s.score,
                base_price=s.base_price,
                up_rate=s.up_rate,
                baseline_up_rate=s.baseline_up_rate,
                ready=s.ready,
                closes=tuple(closes.get(s.ticker, ())),
                price_as_of=price_dates.get(s.ticker),
                volume=volumes.get(s.ticker),
            )
            for s in snapshots
        ]

    async def _recent_closes(
        self, tickers: list[str], limit: int
    ) -> tuple[dict[str, list[float]], dict[str, datetime], dict[str, int]]:
        """티커별 (최근 일봉 종가 과거→최신, 마지막 봉의 세션일, 마지막 봉의 거래량).

        마지막 봉 세션일을 함께 돌려주는 이유: 스냅샷 as_of는 그날 스냅샷이 쓴 봉 기준이고
        여기 종가는 그 뒤에 더 쌓인 봉일 수 있어, 화면이 한 날짜로 뭉뚱그리면 안 된다.
        티커마다 조회하지 않도록 윈도우 함수로 한 번에 받는다.

        거래량은 **마지막 봉만** 쓴다(스파크라인처럼 배열로 두지 않는다) — 화면이 쓰는 것은
        "최근 하루 얼마나 거래됐나" 한 값뿐이고, 30봉치를 실어 보내면 응답만 커진다.
        """
        ranked = (
            select(
                PriceBarOrm.ticker,
                PriceBarOrm.ts,
                PriceBarOrm.close,
                PriceBarOrm.volume,
                func.row_number()
                .over(partition_by=PriceBarOrm.ticker, order_by=PriceBarOrm.ts.desc())
                .label("rn"),
            )
            .where(PriceBarOrm.timeframe == "1d", PriceBarOrm.ticker.in_(tickers))
            .subquery()
        )
        rows = (await self._session.execute(
            select(ranked.c.ticker, ranked.c.ts, ranked.c.close, ranked.c.volume)
            .where(ranked.c.rn <= limit)
            .order_by(ranked.c.ticker, ranked.c.ts.asc())
        )).all()

        out: dict[str, list[float]] = defaultdict(list)
        last_ts: dict[str, datetime] = {}
        last_volume: dict[str, int] = {}
        for ticker, ts, close, volume in rows:
            out[ticker].append(float(close))
            # ts 오름차순이라 마지막 대입이 최신 봉
            last_ts[ticker] = ts
            last_volume[ticker] = int(volume)
        return out, last_ts, last_volume
