"""StockSignalBoardGateway 테스트 — 보드 뷰 → 허브 DTO 변환과 지평·정렬 보존을 고정한다."""
from __future__ import annotations

from datetime import datetime, timezone

from stock.adapter.outbound.gateways.stock_signal_board_gateway import StockSignalBoardGateway
from stock.app.dtos.stock_board_dto import BoardQuery, BoardRowView, BoardView

_NOW = datetime(2026, 9, 3, 6, 0, tzinfo=timezone.utc)


def _row(ticker: str, direction: str) -> BoardRowView:
    return BoardRowView(
        ticker=ticker, name=f"{ticker}명", as_of=_NOW, direction=direction, score=0.4,
        price=100.0, change_pct=0.01, up_rate=0.6, baseline_up_rate=0.55, edge_pct=0.05,
        ready=True, sparkline=(99.0, 100.0), price_as_of=_NOW, volume=10, turnover=1000.0,
    )


class _StubBoard:
    def __init__(self):
        self.queries: list[BoardQuery] = []

    async def board(self, query: BoardQuery) -> BoardView:
        self.queries.append(query)
        return BoardView(horizon_days=query.horizon, rows=(_row("AAA", "UP"), _row("BBB", "DOWN")))


async def test_보드_정렬과_지평을_그대로_허브_DTO로_옮긴다():
    board = _StubBoard()
    info = await StockSignalBoardGateway(board=board).current_board(limit=7)

    assert board.queries == [BoardQuery(horizon=5, limit=7)]
    assert info.horizon_days == 5
    assert [(r.ticker, r.name, r.direction) for r in info.rows] == [
        ("AAA", "AAA명", "UP"), ("BBB", "BBB명", "DOWN"),
    ]
    first = info.rows[0]
    assert (first.price, first.change_pct, first.up_rate, first.baseline_up_rate, first.ready) == (
        100.0, 0.01, 0.6, 0.55, True,
    )
