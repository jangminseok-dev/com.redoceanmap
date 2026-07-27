from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_stats_dto import AreaHeader, ServiceRef
from market.domain.value_objects.area_profile_vo import (
    ApartmentProfile,
    FacilityProfile,
    FloatingRhythm,
    ResidentProfile,
    SalesMix,
    SpendingProfile,
    WorkingProfile,
)


class AreaDetailRepositoryPort(ABC):
    """상권 상세(팩트별 최신 분기 스냅샷) 조회 아웃바운드 포트."""

    @abstractmethod
    async def find_header(self, trdar_code: int) -> AreaHeader | None:
        """상권명 + 자치구명. 상권이 없으면 None."""
        ...

    @abstractmethod
    async def resolve_service(self, trdar_code: int, service_code: str | None) -> ServiceRef | None:
        """업종 확정 — 지정 코드의 이름 조회, 미지정이면 최신 분기 매출 최대 업종."""
        ...

    @abstractmethod
    async def find_sales_mix(self, trdar_code: int, service_code: str) -> SalesMix | None:
        """최신 분기 매출 구조 분해(요일·시간대·성별·연령대)."""
        ...

    @abstractmethod
    async def find_resident(self, trdar_code: int) -> ResidentProfile | None:
        """최신 분기 상주인구(성별×연령대 + 가구)."""
        ...

    @abstractmethod
    async def find_working(self, trdar_code: int) -> WorkingProfile | None:
        """최신 분기 직장인구(성별×연령대)."""
        ...

    @abstractmethod
    async def find_apartment(self, trdar_code: int) -> ApartmentProfile | None:
        """최신 분기 아파트 대표값(단지수·평균시가·평균면적)."""
        ...

    @abstractmethod
    async def find_spending(self, trdar_code: int) -> SpendingProfile | None:
        """최신 분기 소비·소득(카테고리 지출 내림차순)."""
        ...

    @abstractmethod
    async def find_floating_rhythm(self, trdar_code: int) -> FloatingRhythm | None:
        """최신 분기 통행 리듬(주중/주말) — 매출 리듬과 대조해 구매 전환을 본다."""
        ...

    @abstractmethod
    async def find_facility(self, trdar_code: int) -> FacilityProfile | None:
        """최신 분기 집객시설(역·정류장·대학·백화점·병원) — 외부 유입 동선의 앵커."""
        ...
