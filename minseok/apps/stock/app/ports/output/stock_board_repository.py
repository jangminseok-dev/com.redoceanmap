from __future__ import annotations

from abc import abstractmethod

from stock.app.dtos.stock_board_dto import BoardSignalRow
from stock.app.ports.output.risk_report_read_port import RiskReportReadPort


class StockBoardRepositoryPort(RiskReportReadPort):
    """보드 원자료 조회 — 티커별 최신 스냅샷 + 스파크라인용 최근 종가."""

    @abstractmethod
    async def find_latest_signals(self, horizon: int, sparkline_bars: int) -> list[BoardSignalRow]:
        """티커당 최신 as_of 스냅샷 한 줄씩. 스냅샷이 없으면 빈 리스트."""
        ...
