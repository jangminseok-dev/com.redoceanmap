from __future__ import annotations

from hub.app.dtos.stock_signal_board_dto import RiskSignalStat, StockSignalBoardInfo, StockSignalRow
from hub.app.ports.output.stock_signal_board_port import StockSignalBoardPort
from stock.app.dtos.stock_board_dto import BoardQuery
from stock.app.ports.input.stock_board_use_case import StockBoardUseCase

# 신호 지평 — 보드(stock_board 라우터)·StockStatusGateway와 동일.
HORIZON_DAYS = 5


class StockSignalBoardGateway(StockSignalBoardPort):
    """허브의 StockSignalBoardPort를 stock(스포크)이 구현한다 — 보드 유스케이스를 그대로 감싼다.

    종목 예측 화면의 보드와 같은 자료·같은 정렬이어야 채팅 답변과 화면이 어긋나지 않는다.
    """

    def __init__(self, board: StockBoardUseCase) -> None:
        self._board = board

    async def current_board(self, limit: int) -> StockSignalBoardInfo:
        view = await self._board.board(BoardQuery(horizon=HORIZON_DAYS, limit=limit, order="risk"))
        return StockSignalBoardInfo(
            horizon_days=view.horizon_days,
            rows=tuple(
                StockSignalRow(
                    ticker=r.ticker,
                    name=r.name,
                    as_of=r.as_of,
                    direction=r.direction,
                    price=r.price,
                    change_pct=r.change_pct,
                    up_rate=r.up_rate,
                    baseline_up_rate=r.baseline_up_rate,
                    ready=r.ready,
                    rsi=r.rsi,
                    bb_percent_b=r.bb_percent_b,
                    signal_days=r.signal_days,
                    since_signal_pct=r.since_signal_pct,
                    rv20=r.rv20, rv_percentile=r.rv_percentile, vol_state=r.vol_state,
                    trend=r.trend, drawdown_risk=r.drawdown_risk,
                )
                for r in view.rows
            ),
            risk_stats=tuple(
                RiskSignalStat(key=s.key, label=s.label, outcome_label=s.outcome_label, side=s.side,
                               test_rate=s.test_rate, base_rate=s.base_rate, lift=s.lift, n_eff=s.n_eff,
                               validated=s.validated)
                for s in view.risk_stats
            ),
            risk_test_period=view.risk_test_period,
        )
