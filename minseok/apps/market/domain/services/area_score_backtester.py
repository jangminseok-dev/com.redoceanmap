from __future__ import annotations

from dataclasses import dataclass

GRADE_ORDER = ("우수", "양호", "보통", "주의", "위험")
QUINTILE_MIN_N = 25  # 5분위 스프레드 최소 표본 — 분위당 5개는 있어야 평균이 의미 있다


@dataclass(frozen=True)
class ScoredObservation:
    """워크포워드 관측 1건 — 분기 t의 점수와 그 뒤의 실제 결과.

    outcome_closure_next4: t+1~t+4 점포 가중 폐업률(%) — **주 결과**(점수 v2가 가르려는 것, 낮을수록 좋다).
    outcome_rel_floating_qoq: t+1 유동인구 QoQ(상권 − 서울) %p — v1 시절 주 결과, 참고치로 유지.
    outcome_sales_qoq: t+1 매출 QoQ(%) — 참고치.
    """

    trdar_code: str
    year_quarter: int                    # 기준 분기 t
    grade: str
    total: float
    component_scores: dict[str, float]   # key → 0~100 (가용 컴포넌트만)
    outcome_closure_next4: float | None = None
    outcome_rel_floating_qoq: float | None = None
    outcome_sales_qoq: float | None = None


class AreaScoreBacktester:
    """워크포워드 관측 → 집계 리포트(payload dict). 순수 도메인 서비스 — I/O 금지.

    payload 스키마의 단일 정의처다. 저장(JSONB)·조회 게이트웨이는 이 구조를 따른다.
    """

    def aggregate(self, observations: list[ScoredObservation]) -> dict:
        return {
            "n_observations": len(observations),
            "n_areas": len({o.trdar_code for o in observations}),
            "base_quarters": sorted({o.year_quarter for o in observations}),
            "outcome": "closure_next4",
            "grade_outcomes": self._grade_outcomes(observations),
            "component_predictiveness": self._component_predictiveness(observations),
        }

    def _grade_outcomes(self, observations: list[ScoredObservation]) -> list[dict]:
        rows = []
        for grade in GRADE_ORDER:
            group = [o for o in observations if o.grade == grade]
            closures = [o.outcome_closure_next4 for o in group if o.outcome_closure_next4 is not None]
            outcomes = [o.outcome_rel_floating_qoq for o in group if o.outcome_rel_floating_qoq is not None]
            sales = [o.outcome_sales_qoq for o in group if o.outcome_sales_qoq is not None]
            rows.append({
                "grade": grade,
                "n": len(group),
                "avg_closure_next4": self._mean(closures),
                "closure_n": len(closures),
                "avg_rel_floating_qoq": self._mean(outcomes),
                "median_rel_floating_qoq": self._median(outcomes),
                "positive_share": (
                    sum(1 for v in outcomes if v > 0) / len(outcomes) if outcomes else None
                ),
                "avg_sales_qoq": self._mean(sales),
                "sales_n": len(sales),
            })
        return rows

    def _component_predictiveness(self, observations: list[ScoredObservation]) -> list[dict]:
        keys = sorted({k for o in observations for k in o.component_scores})
        rows = []
        for key in keys:
            # 주 결과(향후 4분기 폐업률)의 **부호를 뒤집어** 쓴다 — ρ가 양수면 점수가 높을수록 덜 닫고,
            # 5분위 스프레드는 (점수 하위 20% 폐업률 − 상위 20% 폐업률)%p가 된다
            pairs = [
                (o.component_scores[key], -o.outcome_closure_next4)
                for o in observations
                if key in o.component_scores and o.outcome_closure_next4 is not None
            ]
            scores = [p[0] for p in pairs]
            outcomes = [p[1] for p in pairs]
            rows.append({
                "key": key,
                "n": len(pairs),
                "spearman": self._spearman(scores, outcomes),
                "top_minus_bottom_quintile": self._quintile_spread(pairs),
            })
        return rows

    # ---- 순수 통계 헬퍼 (pandas 반입 금지 — 도메인 순수성) ----

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _median(values: list[float]) -> float | None:
        if not values:
            return None
        s = sorted(values)
        mid = len(s) // 2
        if len(s) % 2 == 1:
            return s[mid]
        return (s[mid - 1] + s[mid]) / 2

    @classmethod
    def _spearman(cls, xs: list[float], ys: list[float]) -> float | None:
        """순위 상관 — 동순위는 평균 순위. 표본 3 미만·상수 시리즈면 None."""
        if len(xs) < 3:
            return None
        rx, ry = cls._avg_ranks(xs), cls._avg_ranks(ys)
        return cls._pearson(rx, ry)

    @staticmethod
    def _avg_ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg_rank = (i + j) / 2 + 1  # 1-기반 평균 순위
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank
            i = j + 1
        return ranks

    @staticmethod
    def _pearson(xs: list[float], ys: list[float]) -> float | None:
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        vx = sum((x - mx) ** 2 for x in xs)
        vy = sum((y - my) ** 2 for y in ys)
        if vx == 0 or vy == 0:
            return None
        return cov / (vx ** 0.5 * vy ** 0.5)

    @classmethod
    def _quintile_spread(cls, pairs: list[tuple[float, float]]) -> float | None:
        """컴포넌트 점수 상위 20% 결과 평균 − 하위 20%(%p). 표본 부족이면 None."""
        if len(pairs) < QUINTILE_MIN_N:
            return None
        by_score = sorted(pairs, key=lambda p: p[0])
        size = len(pairs) // 5
        bottom = [p[1] for p in by_score[:size]]
        top = [p[1] for p in by_score[-size:]]
        return cls._mean(top) - cls._mean(bottom)
