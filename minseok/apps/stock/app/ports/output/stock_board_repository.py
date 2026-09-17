from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from stock.app.dtos.stock_board_dto import BoardSignalRow


class StockBoardRepositoryPort(ABC):
    """보드 원자료 조회 — 티커별 최신 스냅샷 + 스파크라인용 최근 종가."""

    @abstractmethod
    async def find_latest_signals(self, horizon: int, sparkline_bars: int) -> list[BoardSignalRow]:
        """티커당 최신 as_of 스냅샷 한 줄씩. 스냅샷이 없으면 빈 리스트."""
        ...

    async def find_latest_risk_report(self) -> tuple[datetime, dict] | None:
        """위험 신호 검증 리포트 최신 1건(실행 시각, payload). 없으면 None — 구현 전 저장소는 기본값."""
        return None
