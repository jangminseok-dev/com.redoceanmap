from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.stock_status_dto import StockStatusInfo


class StockStatusPort(ABC):
    """지정 종목들의 최신 신호 상태 조회 계약 — recommendation(소비)과 stock(구현)을 잇는다.

    워치리스트 전체를 훑는 stock 내부 보드(stock_board)와 달리 **심볼 집합을 지정해** 묻는다.
    구현은 동결 스냅샷만 읽는다(종목마다 analyze를 부르면 벤더 호출이 심볼 수만큼 난다 —
    stock_board와 같은 이유). 스냅샷이 없는 심볼은 결과에서 빠진다(오류 아님 — 소비자는
    상태 없이 표시하는 열화 동작).
    """

    @abstractmethod
    async def latest_statuses(self, symbols: list[str]) -> dict[str, StockStatusInfo]:
        """요청 심볼 → 최신 상태. 거래소 접미 변형(005930 ↔ 005930.KS)은 구현이 흡수한다."""
        ...

    @abstractmethod
    async def latest_closes(self, symbols: list[str]) -> dict[str, float]:
        """요청 심볼 → 최신 수집 종가(가격 도달 알림 [6]의 판정 근거).

        latest_statuses와 달리 스냅샷 없이도 답한다 — 봉(price_bars)만 있으면 된다.
        타임프레임 무관 최신 봉의 종가(5분봉이 있으면 그것이 최신). 봉이 없는 심볼은
        키 자체가 없다(오류 아님 — 소비자는 판정 불가로 건너뛴다). 벤더 호출 없음.
        """
        ...
