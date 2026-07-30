from __future__ import annotations

from dataclasses import dataclass

from market.domain.value_objects.area_profile_vo import (
    ApartmentProfile,
    FacilityProfile,
    FloatingRhythm,
    PermitChurn,
    ResidentProfile,
    SalesMix,
    ServiceRank,
    SpendingProfile,
    WorkingProfile,
)
from market.domain.value_objects.insight_vo import Insight


@dataclass(frozen=True)
class AreaDetailQuery:
    """상권 상세(최신 분기 구조 분해) 조회 입력 — service_code 생략 시 stats와 동일하게
    최신 분기 매출 최대 업종을 자동 선택한다."""

    trdar_code: int
    service_code: str | None = None


@dataclass(frozen=True)
class AreaDetailView:
    trdar_code: int
    trdar_name: str
    district_name: str
    service_code: str | None  # 매출 팩트가 전혀 없는 상권이면 None
    service_name: str | None
    sales_mix: SalesMix | None
    resident: ResidentProfile | None
    working: WorkingProfile | None
    apartment: ApartmentProfile | None
    spending: SpendingProfile | None
    # 리포지토리가 조회해 서술자에 넘기던 값 — 뷰에 싣지 않아 화면이 차트로 못 그렸다.
    floating: FloatingRhythm | None
    facility: FacilityProfile | None
    # 인허가 대장 기준 업소 교체 — 수집 전이거나 붙은 업소가 없으면 None
    permit_churn: PermitChurn | None
    # 상권 안 업종 랭킹 — 자동 선택된 기준 업종의 근거이기도 하다
    service_ranking: list[ServiceRank]
    insights: list[Insight]
