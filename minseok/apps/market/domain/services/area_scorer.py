from __future__ import annotations

import math

from statistics import median

from market.domain.value_objects.area_score_vo import (
    AreaScore,
    AreaScoreInputs,
    MetricComparison,
    QoqPoint,
    QuarterValue,
    ScoreComponent,
)
from market.domain.value_objects.sales_unit import QUARTER_MONTHS

# 점수 규칙 v2(2026-09-17) — "향후 1년 폐업률"을 가르는 축으로 재설계. 근거는 워크포워드 실험
# (관측 23,009 · 상권 1,646 · 분기 2022Q1~2025Q2, 학습 2022~23 / 검증 2024~25 분할):
#   과거 4분기 폐업률 IC 0.34 · 평균 영업 개월 0.33 · 점포당 매출 수준 0.11 ·
#   v1의 매출·유동인구 QoQ 0.00~0.02(오히려 다음 해 매출과 음의 상관 — 평균회귀)·개폐업 순증 -0.02.
# 검증 기간 종합 IC: v1 0.19 → v2 0.37, 등급별 향후 폐업률 1.9%(우수)→3.8%(위험) 단조.
# 점포 수 전년 대비 증감도 후보였지만 단독 IC -0.05이고 빼는 편이 학습·검증 모두 조금 나아 제외했다.
# 벤치마크는 서울 **중앙 상권**(중앙값) — 합계 평균은 대형 상권에 끌려 50점이 중앙에서 벗어난다.
CLOSURE_DIFF_CAP = 3.0  # 4분기 폐업률 차이(%p) — ±3에서 0/100 포화(서울 5~95% 분위 ±2%p)
PERSISTENCE_RATIO_CAP = 0.5  # 영업 개월 상대비 — 중앙값 대비 ±50%에서 포화
SALES_LEVEL_LOG_CAP = math.log(2)  # 점포당 매출 — 중앙값의 2배/절반에서 포화
WEIGHTS = {"closure_stability": 0.45, "persistence": 0.33, "sales_level": 0.22}
SMALL_SAMPLE_STORES = 5  # 최신 분기 점포가 이보다 적으면 폐업률·점포당 매출·증감률 축을 비운다(표본 튐)


def inputs_from_aggregates(
    *, year_quarter: int, closure_rate_4q: float | None, quarters_with_stores: int,
    store_count: int | None,
    quarterly_sales: float | None, sales_store_count: int | None, operating_months: float | None,
) -> AreaScoreInputs:
    """상권 1곳의 집계값 → 점수 v2 입력. 런타임(PG 리포지토리)과 백테스트 스크립트가 **같은 규칙**을 쓰게 한 단일 정의처.

    closure_rate_4q는 최근 4분기 점포 가중 폐업률(%) — 4분기가 다 있을 때만 쓴다.
    quarterly_sales는 서울시 추정매출 원값(분기 합계) — 월 환산(÷3)·만원 단위는 여기서.
    """
    small = store_count is None or store_count < SMALL_SAMPLE_STORES
    sales = None
    if not small and quarterly_sales and sales_store_count:
        sales = quarterly_sales / QUARTER_MONTHS / sales_store_count / 10_000
    return AreaScoreInputs(
        year_quarter=year_quarter,
        closure_rate_4q=float(closure_rate_4q) if not small and quarters_with_stores == 4 and closure_rate_4q is not None else None,
        operating_months=float(operating_months) if operating_months is not None else None,
        sales_per_store_wan=sales,
    )


def median_inputs(year_quarter: int, inputs: list[AreaScoreInputs]) -> AreaScoreInputs | None:
    """시도 안 상권들의 축별 중앙값 — 점수 v2의 벤치마크(50점 = 서울 중앙 상권)."""
    if not inputs:
        return None

    def med(attr: str) -> float | None:
        values = [v for i in inputs if (v := getattr(i, attr)) is not None]
        return median(values) if values else None

    return AreaScoreInputs(
        year_quarter=year_quarter, closure_rate_4q=med("closure_rate_4q"), operating_months=med("operating_months"),
        sales_per_store_wan=med("sales_per_store_wan"),
    )

GRADE_BOUNDS = ((80.0, "우수"), (65.0, "양호"), (45.0, "보통"), (30.0, "주의"))

# 조회 가능한 최대 분기 수. **짧은 쪽(매출·점포 20분기)에 맞춘다** — 인구·소비 팩트는
# 28분기지만, 시계열을 병합해 보여주는 화면에서 상한을 28로 두면 앞 8분기가 매출 없는
# 반쪽 시계열이 된다. 라우터 상한·시도 벤치마크 캐시 창이 이 값을 공유한다.
MAX_QUARTERS = 20


def prev_quarter(year_quarter: int) -> int:
    """직전 분기 코드 — 20251 → 20244, 20252 → 20251."""
    year, quarter = divmod(year_quarter, 10)
    if quarter == 1:
        return (year - 1) * 10 + 4
    return year_quarter - 1


def last_four_quarters(year_quarter: int) -> list[int]:
    """year_quarter 포함 최근 4분기 — 점포 가중 1년 폐업률의 창. 판정용 폐업률의 단일 정의처(2026-09-17).

    한 분기 폐업률은 정수(%)라 서울 상권 절반 이상이 0%이고, 향후 1년 폐업률과의 분기 내 순위상관이
    0.14에 그친다. 최근 4분기 점포 가중(Σ폐업 점포 ÷ Σ점포)은 0.34다.
    """
    out = [year_quarter]
    for _ in range(3):
        out.append(prev_quarter(out[-1]))
    return out


def prev_year_quarter(year_quarter: int) -> int:
    """전년 동분기 코드 — 20244 → 20234.

    코드 형식이 `연도 × 10 + 분기`라 1년 전은 **-10**이다(-10000이 아니다).
    """
    return year_quarter - 10


class AreaScorer:
    """상권 추이(QoQ·YoY)와 서울 중앙 상권 대비 종합점수를 계산하는 순수 도메인 서비스.

    점수 규칙 v2 — 모듈 상단 주석(근거 실험)과 `score()` 참고. 추이 계산은 화면 표시용으로 점수와 분리돼 있다.
    """

    def qoq_series(self, series: list[QuarterValue]) -> list[QoqPoint]:
        """분기별 직전 분기 대비 변화율(%) — 직전 분기 결측·0 이하·비연속이면 None."""
        by_quarter = {p.year_quarter: p.value for p in series}
        points = []
        for p in sorted(series, key=lambda x: x.year_quarter):
            prev = by_quarter.get(prev_quarter(p.year_quarter))
            rate = None
            if prev is not None and prev > 0:
                rate = round((p.value - prev) / prev * 100, 2)
            points.append(QoqPoint(year_quarter=p.year_quarter, value=p.value, qoq_rate=rate))
        return points

    def yoy_series(self, series: list[QuarterValue]) -> list[QoqPoint]:
        """전년 동분기 대비 변화율(%) — `qoq_series`와 같은 구조, 참조 분기만 -1년.

        소매 분기 데이터는 계절성이 지배적이라 QoQ만 보면 **모든 상권의 1분기가
        폭락으로 보인다**(4분기 대비). 20분기가 있어야 성립하는 축이다.
        `QoqPoint.qoq_rate` 필드를 그대로 쓰되 의미는 YoY다 — 소비자가 구분해 쓴다.
        """
        by_quarter = {p.year_quarter: p.value for p in series}
        points = []
        for p in sorted(series, key=lambda x: x.year_quarter):
            base = by_quarter.get(prev_year_quarter(p.year_quarter))
            rate = None
            if base is not None and base > 0:
                rate = round((p.value - base) / base * 100, 2)
            points.append(QoqPoint(year_quarter=p.year_quarter, value=p.value, qoq_rate=rate))
        return points

    def score(
        self,
        *,
        closure_stability: MetricComparison | None,
        persistence: MetricComparison | None,
        sales_level: MetricComparison | None,
    ) -> AreaScore | None:
        """v2 — 컴포넌트별 0~100(50 = 서울 중앙 상권), 총점은 가용 컴포넌트의 가중 평균(결측은 가중치째 제외).

        closure_stability: 최근 4분기 점포 가중 폐업률(%) vs 서울 중앙값 — **낮을수록** 높은 점수
        persistence: 평균 영업 개월 vs 서울 중앙값 — 상대비
        sales_level: 점포당 월매출(만원) vs 서울 중앙값 — 로그 비
        """
        components = [
            c for c in (
                self._lower_is_better_component(
                    "closure_stability", "폐업 안정성", closure_stability, CLOSURE_DIFF_CAP,
                ),
                self._ratio_component("persistence", "영업 지속성", persistence, PERSISTENCE_RATIO_CAP),
                self._log_ratio_component("sales_level", "점포당 매출 수준", sales_level, SALES_LEVEL_LOG_CAP),
            )
            if c is not None
        ]
        if not components:
            return None
        weight = sum(WEIGHTS[c.key] for c in components)
        total = round(sum(c.score * WEIGHTS[c.key] for c in components) / weight, 1)
        return AreaScore(total=total, grade=self._grade(total), components=tuple(components))

    def _lower_is_better_component(
        self, key: str, name: str, comparison: MetricComparison | None, cap: float,
    ) -> ScoreComponent | None:
        if comparison is None:
            return None
        diff = comparison.benchmark - comparison.value  # 벤치마크보다 낮으면 +
        return ScoreComponent(
            key=key, name=name, score=self._clamp(50 + 50 * diff / cap),
            value=comparison.value, benchmark=comparison.benchmark,
        )

    def _ratio_component(
        self, key: str, name: str, comparison: MetricComparison | None, cap: float
    ) -> ScoreComponent | None:
        if comparison is None or comparison.benchmark <= 0:
            return None
        score = self._clamp(50 + 50 * (comparison.value / comparison.benchmark - 1) / cap)
        return ScoreComponent(
            key=key, name=name, score=score,
            value=comparison.value, benchmark=comparison.benchmark,
        )

    def _log_ratio_component(
        self, key: str, name: str, comparison: MetricComparison | None, cap: float
    ) -> ScoreComponent | None:
        if comparison is None or comparison.value <= 0 or comparison.benchmark <= 0:
            return None
        score = self._clamp(50 + 50 * math.log(comparison.value / comparison.benchmark) / cap)
        return ScoreComponent(
            key=key, name=name, score=score,
            value=comparison.value, benchmark=comparison.benchmark,
        )

    @staticmethod
    def _clamp(score: float) -> float:
        return round(min(100.0, max(0.0, score)), 1)

    @staticmethod
    def _grade(total: float) -> str:
        for bound, grade in GRADE_BOUNDS:
            if total >= bound:
                return grade
        return "위험"
