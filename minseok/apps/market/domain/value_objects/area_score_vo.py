from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuarterValue:
    """분기 1개의 측정값 — 시계열 계산 입력 단위."""

    year_quarter: int
    value: float


@dataclass(frozen=True)
class QoqPoint:
    """분기 값 + 직전 분기 대비 변화율(%) — 직전 분기 결측·0·비연속이면 None."""

    year_quarter: int
    value: float
    qoq_rate: float | None


@dataclass(frozen=True)
class MetricComparison:
    """상권 값 vs 서울 중앙 상권 값 — 스코어 컴포넌트 계산 입력."""

    value: float
    benchmark: float


@dataclass(frozen=True)
class ScoreComponent:
    """컴포넌트 1개의 점수 — 50이 서울 중앙 상권 동률, 0~100."""

    key: str
    name: str
    score: float
    value: float
    benchmark: float


@dataclass(frozen=True)
class AreaScore:
    total: float  # 가용 컴포넌트 가중 평균 (0~100, v2 가중치 WEIGHTS)
    grade: str  # 우수 / 양호 / 보통 / 주의 / 위험
    components: tuple[ScoreComponent, ...]


@dataclass(frozen=True)
class AreaScoreInputs:
    """점수 v2 입력 — 최신 점포 분기 기준 상권 1곳의 값(또는 서울 중앙값). 산출 불가 축은 None.

    closure_rate_4q: 최근 4분기 점포 가중 폐업률(%) — 4분기가 다 있고 최신 점포 5개 이상일 때만
    operating_months: 평균 영업 개월
    sales_per_store_wan: 점포당 월매출(만원) — 분기 합계 ÷ 3, 최신 점포 5개 이상일 때만
    """

    year_quarter: int
    closure_rate_4q: float | None
    operating_months: float | None
    sales_per_store_wan: float | None
