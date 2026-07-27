from __future__ import annotations

from market.domain.value_objects.area_score_vo import (
    AreaScore,
    MetricComparison,
    QoqPoint,
    QuarterValue,
    ScoreComponent,
)

GROWTH_DIFF_CAP = 20.0  # 성장률 차이(%p) — ±20에서 0/100 포화
HEALTH_DIFF_CAP = 10.0  # 개폐업 순증률 차이(%p) — ±10에서 포화
PERSISTENCE_RATIO_CAP = 0.5  # 영업 개월 상대비 — 벤치마크 대비 ±50%에서 포화

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


class AreaScorer:
    """상권 QoQ 추이와 시도 벤치마크 대비 종합점수를 계산하는 순수 도메인 서비스.

    점수 규칙 v1 — 컴포넌트별 0~100, 50 = 벤치마크 동률:
    - 성장률(매출·유동인구)·개폐업 건강도: 벤치마크와의 차이(%p)를 캡 기준 선형 매핑
    - 영업 지속성: 벤치마크 대비 상대비를 캡 기준 선형 매핑
    총점 = 가용 컴포넌트 단순 평균(결측 컴포넌트 제외). 전부 결측이면 None.
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

    def growth_comparison(
        self, area: list[QoqPoint], benchmark: list[QoqPoint]
    ) -> MetricComparison | None:
        """상권의 최신 유효 QoQ와 같은 분기의 벤치마크 QoQ를 짝짓는다 — 짝이 없으면 None."""
        latest = next((p for p in reversed(area) if p.qoq_rate is not None), None)
        if latest is None:
            return None
        bench_rate = next(
            (p.qoq_rate for p in benchmark
             if p.year_quarter == latest.year_quarter and p.qoq_rate is not None),
            None,
        )
        if bench_rate is None:
            return None
        return MetricComparison(value=latest.qoq_rate, benchmark=bench_rate)

    def score(
        self,
        *,
        sales_growth: MetricComparison | None,
        floating_growth: MetricComparison | None,
        store_health: MetricComparison | None,
        persistence: MetricComparison | None,
    ) -> AreaScore | None:
        components = [
            c for c in (
                self._diff_component("sales_growth", "매출 성장", sales_growth, GROWTH_DIFF_CAP),
                self._diff_component(
                    "floating_growth", "유동인구 성장", floating_growth, GROWTH_DIFF_CAP
                ),
                self._diff_component(
                    "store_health", "개폐업 건강도", store_health, HEALTH_DIFF_CAP
                ),
                self._ratio_component(
                    "persistence", "영업 지속성", persistence, PERSISTENCE_RATIO_CAP
                ),
            )
            if c is not None
        ]
        if not components:
            return None
        total = round(sum(c.score for c in components) / len(components), 1)
        return AreaScore(total=total, grade=self._grade(total), components=tuple(components))

    def _diff_component(
        self, key: str, name: str, comparison: MetricComparison | None, cap: float
    ) -> ScoreComponent | None:
        if comparison is None:
            return None
        score = self._clamp(50 + 50 * (comparison.value - comparison.benchmark) / cap)
        return ScoreComponent(
            key=key, name=name, score=score,
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

    @staticmethod
    def _clamp(score: float) -> float:
        return round(min(100.0, max(0.0, score)), 1)

    @staticmethod
    def _grade(total: float) -> str:
        for bound, grade in GRADE_BOUNDS:
            if total >= bound:
                return grade
        return "위험"
