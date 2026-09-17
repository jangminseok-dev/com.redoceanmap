from __future__ import annotations

from dataclasses import dataclass

from market.domain.value_objects.area_score_vo import AreaScore


@dataclass(frozen=True)
class AreaScoreQuery:
    """상권 종합점수 조회 입력 — quarters는 추이 구간(QoQ는 구간 첫 분기 제외)."""

    trdar_code: int
    quarters: int = 8


@dataclass(frozen=True)
class AreaScoreHeader:
    trdar_code: int
    trdar_name: str
    district_name: str
    sido_code: str | None  # 시도 벤치마크 조회 키 (지역 계층 미연결 상권이면 None)


@dataclass(frozen=True)
class TrendPoint:
    """분기 1개의 추이 — 값과 직전 분기 대비 변화율(%). 팩트별 결측은 None."""

    year_quarter: int
    monthly_sales: int | None = None
    sales_qoq: float | None = None
    total_floating_pop: int | None = None
    floating_qoq: float | None = None
    # 전년 동분기 대비 — 계절성이 큰 분기 데이터에서 QoQ보다 정직하다(20분기가 있어야 성립)
    sales_yoy: float | None = None
    floating_yoy: float | None = None


@dataclass(frozen=True)
class AreaScoreView:
    trdar_code: int
    trdar_name: str
    district_name: str
    score: AreaScore | None  # 산출 근거 팩트가 전혀 없으면 None
    trend: list[TrendPoint]  # year_quarter 오름차순
