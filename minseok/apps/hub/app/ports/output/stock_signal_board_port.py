from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.stock_signal_board_dto import StockSignalBoardInfo


class StockSignalBoardPort(ABC):
    """워치리스트 신호 보드 조회 계약 — chat(소비)과 stock(구현)을 잇는다.

    StockStatusPort가 **심볼 집합을 지정해** 묻는 것과 달리 워치리스트 전체를 보드 정렬로
    돌려준다(종목 예측 화면의 보드와 같은 자료). 구현은 동결 스냅샷만 읽는다 — 벤더 호출 없음.
    """

    @abstractmethod
    async def current_board(self, limit: int) -> StockSignalBoardInfo:
        """최신 스냅샷 기준 상위 limit행. 스냅샷이 없으면 rows가 빈 보드(오류 아님)."""
        ...
