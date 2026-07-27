"""상권 데이터 계약 DTO.

허브(hub)가 공개하는 앱 간 협력 계약의 일부. market(스포크)이 채워서 반환하고
chat(스포크)이 소비한다. 원시 수치만 담으며(텍스트 포맷팅은 소비자 관심사),
외부 의존 없는 순수 도메인 객체다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceCode:
    code: str
    name: str


@dataclass(frozen=True)
class AreaInfo:
    trdar_code: int
    trdar_name: str
    district_name: str
    adm_dong_name: str
    lat: float
    lng: float


@dataclass(frozen=True)
class AreaSummary:
    areas: list[AreaInfo]
    latest_quarter: int | None
    sales_by_code: dict[int, int]


@dataclass(frozen=True)
class AreaOverviewRow:
    """어드민 상권 목록 1행 — 최신 분기 기준 집계. 팩트가 없는 항목은 None."""

    trdar_code: int
    trdar_name: str
    gu_name: str
    dong_name: str
    store_count: int | None
    closure_rate: float | None  # 업종별 팩트의 단순평균 — 어드민 목록 표시 용도
    monthly_sales: int | None


@dataclass(frozen=True)
class AreaScoreComponent:
    """종합점수 컴포넌트 1개 — 50점 = 시도 벤치마크 동률, 0~100."""

    key: str  # sales_growth / floating_growth / store_health / persistence
    name: str
    score: float
    value: float
    benchmark: float


@dataclass(frozen=True)
class AreaScoreInfo:
    """상권 1곳의 시도 벤치마크 대비 종합점수(0~100)."""

    total: float
    grade: str  # 우수 / 양호 / 보통 / 주의 / 위험
    components: tuple[AreaScoreComponent, ...]


@dataclass(frozen=True)
class AreaRawStat:
    """상권 1곳의 원시 통계(특정 업종·분기). 값이 없으면 None, 존재 여부는 has_* 로 표기."""

    # 매출 (EstimatedSales)
    has_sales: bool
    monthly_sales_amount: int | None
    weekday_sales_amount: int | None
    # 점포 (Store)
    has_store: bool
    store_count: int | None
    closure_rate: float | None
    opening_rate: float | None
    franchise_store_count: int | None
    # 유동인구 (FloatingPopulation)
    has_fp: bool
    total_floating_pop: int | None
    age_10_floating_pop: int | None
    age_20_floating_pop: int | None
    age_30_floating_pop: int | None
    age_40_floating_pop: int | None
    age_50_floating_pop: int | None
    age_60_plus_floating_pop: int | None
    time_00_06_floating_pop: int | None
    time_06_11_floating_pop: int | None
    time_11_14_floating_pop: int | None
    time_14_17_floating_pop: int | None
    time_17_21_floating_pop: int | None
    time_21_24_floating_pop: int | None
    # 상권변화 (CommercialChange) — region_*는 상권이 속한 시도의 벤치마크 평균
    has_cc: bool
    change_indicator_name: str | None
    operating_months_avg: float | None
    region_operating_months_avg: float | None
