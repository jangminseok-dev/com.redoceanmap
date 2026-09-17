from __future__ import annotations

from abc import ABC, abstractmethod

from market.domain.value_objects.finance_vo import KeyMoneyBenchmark, RentBenchmark


class AreaFinanceRepositoryPort(ABC):
    """재무 엔진 전용 조회 — 임대료(매칭 포함)·금리. 점포당 매출·창업비용은 AreaDetailRepositoryPort 재사용."""

    @abstractmethod
    async def find_rent(self, trdar_code: int) -> RentBenchmark | None:
        """소규모 상가 최신 분기 임대료 — 상권 직접 매칭 → 자치구 권역 → 서울 순. 미적재면 None."""
        ...

    @abstractmethod
    async def find_key_money(self, industry_group: str) -> KeyMoneyBenchmark | None:
        """서울 업종 대분류의 최신 연도 권리금 — 미적재면 None."""
        ...

    @abstractmethod
    async def find_loan_rate(self) -> tuple[int, float] | None:
        """(연월, 연 %) — ECOS 121Y006 '대출평균' 최신월. 미적재면 None."""
        ...
