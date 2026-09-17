from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GradeOutcomeRow:
    """등급별 다음 분기 실제 결과 — 등급이 미래를 갈랐는지의 실측."""

    grade: str                          # 우수 / 양호 / 보통 / 주의 / 위험
    n: int
    avg_rel_floating_qoq: float | None      # t+1 상대 유동인구 QoQ(%p, 상권−서울) 평균
    median_rel_floating_qoq: float | None
    positive_share: float | None            # 결과가 양(+)인 비율
    avg_sales_qoq: float | None             # t+1 매출 QoQ(%) 평균 — 참고치
    sales_n: int
    avg_closure_next4: float | None = None  # 점수 v2 주 결과 — t+1~t+4 점포 가중 폐업률(%) 평균(구버전 리포트는 None)
    closure_n: int = 0


@dataclass(frozen=True)
class ComponentRow:
    """컴포넌트 점수(t)의 다음 분기 결과(t+1) 예측력."""

    key: str                               # 점수 v2: closure_stability / persistence / sales_level
    n: int
    spearman: float | None                 # 컴포넌트 점수 ↔ 향후 4분기 폐업률(부호 반전)의 순위 상관 — 양수면 점수가 높을수록 덜 닫음
    top_minus_bottom_quintile: float | None  # 점수 하위 20% 폐업률 − 상위 20% 폐업률(%p) — 양수면 예측이 맞는 방향


@dataclass(frozen=True)
class AreaBacktestReportInfo:
    """상권 점수 워크포워드 백테스트 리포트 — 최신 실행 1건."""

    ran_at: datetime
    params: dict
    n_observations: int
    n_areas: int
    base_quarters: list[int]
    grade_outcomes: list[GradeOutcomeRow]
    component_predictiveness: list[ComponentRow]
