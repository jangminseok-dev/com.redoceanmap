"""주식 확률·예측 요약 계약 DTO.

허브가 공개하는 앱 간 협력 계약. stock(스포크)이 채워서 반환하고 chat(스포크)이
"결론 한 줄"(방향 신호 + 과거 통계) 산출에 소비한다. 원시 통계만 담으며(문장화는 소비자 몫),
페이지 verdict()와 같은 재료(up_rate·baseline·ready·표본·CI)를 챗 경로에도 준다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockRiskEvidence:
    key: str            # vol_high | vol_low | drop_high | drop_low
    test_rate: float    # 검증 구간에서 그 결과가 나온 비율
    base_rate: float    # 평소 비율


@dataclass(frozen=True)
class StockRiskSummary:
    """위험 신호 — 방향과 달리 검증 구간에서도 유지된 축(2026-09-17). 결론 한 줄이 중립일 때 앞세운다.
    evidence는 학습·검증 두 구간 모두 통과한 실측만(없으면 빈 튜플 — 소비자는 수치 없이 상태만 말한다)."""

    vol_state: str          # HIGH | NORMAL | LOW
    drawdown_risk: str      # HIGH | NORMAL | LOW
    rv_percentile: float    # 자기 1년 분포 안 위치(0~1)
    evidence: tuple[StockRiskEvidence, ...] = ()


@dataclass(frozen=True)
class StockForecastSummary:
    signal_direction: str          # UP | DOWN | NEUTRAL (지표 신호 기준, 감성 미반영)
    ready: bool = False            # n≥100 + Wilson 하한이 기준선 넘음 (통계적 유의)
    up_rate: float | None = None   # 같은 신호 과거 상승 비율 (표본 없으면 None)
    baseline_up_rate: float | None = None  # 평소(무조건부) 상승 비율
    sample_size: int = 0
    hits: int = 0
    ci_low: float | None = None    # Wilson 95% 하한
    ci_high: float | None = None   # Wilson 95% 상한
    risk: StockRiskSummary | None = None  # 위험 신호 — 봉이 모자라면 None
