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
# 같은 방향 신호의 연속 일수를 세는 창 — 연속이 이보다 길면 창 끝에서 자른다
STREAK_LOOKBACK_DAYS = 45


def _streak(rows_desc: list) -> tuple[int, float | None]:
    """최신부터 같은 방향이 끊기지 않고 이어진 스냅샷 수와 그 첫 스냅샷의 기준가.

    9/17 신호 보드 감사: 상승 신호의 45%가 같은 종목 3일 내 반복이었다 — 화면이 매일 새 신호처럼 보이면
    "상승 신호인데 계속 떨어진다"로 읽힌다. 연속 일수와 첫 신호 이후 등락을 함께 보여주기 위한 값.
    """
    direction = rows_desc[0].direction
    count, start = 0, rows_desc[0]
    for row in rows_desc:
        if row.direction != direction:
            break
        count, start = count + 1, row
    return count, start.base_price


class StockBoardPgRepository(StockBoardRepositoryPort):
    """forecast_snapshots(티커별 최신) + price_bars(최근 종가) 두 번의 조회로 보드를 만든다.

    종목마다 analyze/forecast를 부르면 워치리스트 크기만큼 벤더 호출이 나므로,
    이미 일일 cron이 동결해 둔 스냅샷만 읽는다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_latest_signals(self, horizon: int, sparkline_bars: int) -> list[BoardSignalRow]:
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=STALE_AFTER_DAYS)
        # 연속 일수를 세려고 최근 STREAK_LOOKBACK_DAYS치를 함께 읽는다 — 티커당 수십 행이라 가볍다
        recent = (await self._session.execute(
            select(ForecastSnapshotOrm)
            .where(
                ForecastSnapshotOrm.horizon_days == horizon,
                ForecastSnapshotOrm.as_of >= now - timedelta(days=STREAK_LOOKBACK_DAYS),
            )
            .order_by(ForecastSnapshotOrm.ticker, ForecastSnapshotOrm.as_of.desc())
        )).scalars().all()
        by_ticker: dict[str, list[ForecastSnapshotOrm]] = {}
        for s in recent:
            by_ticker.setdefault(s.ticker, []).append(s)
        latest = {t: rows[0] for t, rows in by_ticker.items() if rows[0].as_of >= cutoff}
        snapshots = list(latest.values())
        if not snapshots:
            return []
        streaks = {t: _streak(by_ticker[t]) for t in latest}

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
                rsi=s.rsi,
                bb_percent_b=s.bb_percent_b,
                signal_days=streaks[s.ticker][0],
                signal_start_price=streaks[s.ticker][1],
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
