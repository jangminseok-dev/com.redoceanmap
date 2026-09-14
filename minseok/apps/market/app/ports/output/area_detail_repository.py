from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_stats_dto import AreaHeader, ServiceRef
from market.domain.value_objects.area_profile_vo import (
    ApartmentProfile,
    ChangeProfile,
    FacilityProfile,
    FloatingRhythm,
    PermitChurn,
    ResidentProfile,
    SalesMix,
    ServiceRank,
    SpendingProfile,
    StartupCost,
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
    async def find_service_ranking(self, trdar_code: int, limit: int = 12) -> list[ServiceRank]:
        """상권 안 업종 랭킹(최신 분기, 매출 내림차순) — 자동 선택된 업종의 근거이기도 하다."""
        ...

    @abstractmethod
    async def find_facility(self, trdar_code: int) -> FacilityProfile | None:
        """최신 분기 집객시설(역·정류장·대학·백화점·병원) — 외부 유입 동선의 앵커."""
        ...

    @abstractmethod
    async def find_change(self, trdar_code: int) -> ChangeProfile | None:
        """최신 분기 상권변화지표(+시도 벤치마크 영업개월) — 팩트 없으면 None(문장 생략)."""
        ...

    @abstractmethod
    async def find_asset_price(self, trdar_code: int, months: int = 12) -> "AssetPrice | None":
        """상권이 속한 자치구의 상가·업무용 매매 평단가(실거래) — 진입 비용 축.

        원본에 좌표가 없어 자치구 단위 집계다. 데이터 없으면 None(문장 생략).
        """
        ...

    @abstractmethod
    async def find_permit_churn(
        self, trdar_code: int, months: int = 12, sample: int = 5
    ) -> PermitChurn | None:
        """인허가 대장 기준 업소 교체 — 분기 팩트가 못 주는 '업소 단위·임의 기간' 축.

        좌표로 상권에 붙인 업소만 센다(반경 밖·좌표 없음은 애초에 trdar_code가 NULL).
        수집 전이거나 붙은 업소가 없으면 None — 화면은 해당 섹션을 통째로 생략한다.
        """
        ...

    @abstractmethod
    async def find_startup_cost(self, industry_name: str) -> StartupCost | None:
        """공정위 업종(중분류)별 창업비용 — 최신 적재 연도. 미적재·없는 업종은 None(문장 생략)."""
        ...
