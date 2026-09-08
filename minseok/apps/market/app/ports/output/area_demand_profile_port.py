from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_demand_profile_dto import AreaDemandProfile


class AreaDemandProfilePort(ABC):
    """상권 수요 분포 조회 아웃바운드 포트 — 입지 적합도의 입력 팩트."""

    @abstractmethod
    async def latest_quarter(self) -> int | None:
        """매출 팩트의 최신 적재 분기. 적재 전이면 None."""
        ...

    @abstractmethod
    async def get_demand_profile(
        self, trdar_code: int, service_code: str, year_quarter: int
    ) -> AreaDemandProfile | None:
        """상권 1곳 × 업종 1개의 수요 분포. 상권·업종이 없으면 None."""
        ...
