from __future__ import annotations

from abc import ABC, abstractmethod

from stock.domain.entities.price_bar import PriceBar


class ForecastHistoryPort(ABC):
    """예측용 일봉 전체 조회 아웃바운드 포트 — 워크포워드 백테스트 재료."""

    @abstractmethod
    async def find_latest_daily_bar(self, symbol: str) -> PriceBar | None:
        """마지막 1d 봉 1건 — 캐시 검사용 경량 조회(티커 확정 + 최신 ts). 미보유면 None."""
        ...

    @abstractmethod
    async def find_all_daily_bars(self, symbol: str) -> list[PriceBar]:
        """저장된 1d 봉 전체(ts 오름차순). 접미 매칭(005930 ↔ 005930.KS)은 구현이 맡는다.
        미보유 심볼이면 빈 리스트."""
        ...

    async def find_recent_daily_bars(self, symbol: str, limit: int) -> list[PriceBar]:
        """최근 limit개 1d 봉(ts 오름차순) — 실시간 분석의 지표 입력. 백테스트가 아니라 지표만 계산하므로 전체가 필요 없다.
        기본 구현은 전체에서 자른다 — 저장소 구현은 쿼리에서 자르는 편이 빠르다(KO 16,287봉 267ms)."""
        return (await self.find_all_daily_bars(symbol))[-limit:]
