from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AreaRankingQuery:
    """상권 랭킹 조회 입력 — 전부 선택. 미지정이면 서울 전 상권."""

    district_name: str | None = None
    division_code: str | None = None  # 골목/발달/전통시장/관광특구
    service_code: str | None = None   # 지정 시 해당 업종만 집계("카페 하기 좋은 상권")


@dataclass(frozen=True)
class AreaRankingRow:
    """상권 1곳의 랭킹 행 — 팩트가 없는 축은 None(정렬은 소비자 몫)."""

    trdar_code: int
    trdar_name: str
    district_name: str
    dong_name: str
    division_code: str
    division_name: str
    lat: float
    lng: float
    monthly_sales: int | None
    store_count: int | None
    # 규모 큰 상권이 항상 좋은 게 아니다 — 점포당 매출이 "돈이 되는가"의 단일 최고 지표
    sales_per_store: int | None
    sales_qoq: float | None       # 직전 분기 대비 %, 직전 분기 결측이면 None
    closure_rate: float | None
    area_size: float | None  # ㎡ — 밀도 정규화용


@dataclass(frozen=True)
class ServiceOption:
    code: str
    name: str


@dataclass(frozen=True)
class AreaRankingView:
    year_quarter: int | None  # 집계 기준 분기(데이터 없으면 None)
    rows: list[AreaRankingRow]
    # 이 엔드포인트 자신의 필터 어휘 — 목록 하나 때문에 라우터를 새로 만들지 않는다
    services: list[ServiceOption]
