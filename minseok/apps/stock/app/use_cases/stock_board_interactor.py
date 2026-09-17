from __future__ import annotations

from stock.app.dtos.stock_board_dto import BoardQuery, BoardRowView, BoardSignalRow, BoardView
from stock.app.ports.input.stock_board_use_case import StockBoardUseCase
from stock.app.ports.output.stock_board_repository import StockBoardRepositoryPort
from stock.app.ports.output.symbol_directory_port import SymbolDirectoryPort
from stock.domain.services.board_ranker import sort_key

# 스파크라인 한 줄에 그릴 종가 개수 — 30거래일이면 약 6주 흐름이 보인다
SPARKLINE_BARS = 30


class StockBoardInteractor(StockBoardUseCase):
    """신호 보드 대장 — 스냅샷 조회 → 이름 붙이기 → 도메인 정렬 규칙으로 줄 세우기."""

    def __init__(
        self,
        repository: StockBoardRepositoryPort,
        directory: SymbolDirectoryPort,
    ) -> None:
        self._repository = repository
        self._directory = directory

    async def board(self, query: BoardQuery) -> BoardView:
        rows = await self._repository.find_latest_signals(query.horizon, SPARKLINE_BARS)
        ranked = sorted(rows, key=lambda r: sort_key(r.direction, r.score, r.ticker))
        views = tuple(self._to_view(row) for row in ranked[: query.limit])
        return BoardView(horizon_days=query.horizon, rows=views)

    def _to_view(self, row: BoardSignalRow) -> BoardRowView:
        # 최신 종가는 스냅샷 시점의 base_price가 아니라 실제 마지막 봉 — 스냅샷은
        # 하루 한 번이라 그 사이 봉이 더 쌓였을 수 있다. 봉이 없으면 base_price로 열화.
        price = row.closes[-1] if row.closes else row.base_price
        previous = row.closes[-2] if len(row.closes) >= 2 else None
        edge = (
            row.up_rate - row.baseline_up_rate
            if row.up_rate is not None and row.baseline_up_rate is not None
            else None
        )
        return BoardRowView(
            ticker=row.ticker,
            name=self._directory.display_name(row.ticker),
            as_of=row.as_of,
            direction=row.direction,
            score=row.score,
            price=price,
            change_pct=(price / previous - 1.0) if previous else None,
            up_rate=row.up_rate,
            baseline_up_rate=row.baseline_up_rate,
            edge_pct=edge,
            ready=row.ready,
            sparkline=row.closes,
            price_as_of=row.price_as_of,
            volume=row.volume,
            # 거래대금은 마지막 봉의 종가 × 거래량이다. 정확한 체결 합계가 아니라 근사치이며,
            # 통화가 종목마다 다르므로 화면이 심볼로 단위를 붙인다.
            turnover=price * row.volume if row.volume is not None else None,
            rsi=row.rsi,
            bb_percent_b=row.bb_percent_b,
            signal_days=row.signal_days,
            since_signal_pct=(price / row.signal_start_price - 1.0) if row.signal_start_price else None,
        )
