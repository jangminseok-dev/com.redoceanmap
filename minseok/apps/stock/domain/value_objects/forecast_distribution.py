from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DirectionStats:
    """같은 방향 신호일들의 horizon일 뒤 실적 통계 + 구간 내 하방·회복 통계.

    마감 수익률(q25/median/q75)은 "결국 어디서 끝났나"만 말한다. 하방 필드는 그 사이에
    **얼마나 빠졌다가** 어떻게 됐는지를 담는다 — 같은 +1% 마감도 무조정 상승과 -8% 급락 후
    회복은 전혀 다른 경험이다. 하락 방향 예측이 검증되지 않았으므로(재채점 2·3차) 하방은
    방향 라벨이 아니라 이 실측 분포로 제시한다.
    """

    sample_size: int
    hits: int              # 상승 마감(양의 수익률) 수
    q25: float | None      # 실현 수익률 분위수 — 표본 2개 미만이면 None
    median: float | None
    q75: float | None
    # --- 구간 내 하방(장중 저가 기준) · 회복 ---
    trough_median_pct: float | None = None  # 장중 최대 낙폭 중앙값 (-0.032 = -3.2%)
    trough_q25_pct: float | None = None     # 하위 25% = 더 나쁜 쪽
    down_close_rate: float | None = None    # horizon 마감이 음수였던 비율
    dip_samples: int = 0                    # 낙폭이 있었던(trough < 0) 표본 — 회복률의 분모
    recovery_rate: float | None = None      # dip_samples 중 기준가를 종가로 회복한 비율
    recovery_days_median: float | None = None  # 회복까지 걸린 거래일 중앙값


@dataclass(frozen=True, slots=True)
class RegimeStats:
    """레짐 1개 슬라이스의 분포 — 조건부 ready 판정에는 조건부 기준선이 필요하다."""

    evaluated: int
    baseline_up_rate: float
    by_direction: dict[str, DirectionStats]


@dataclass(frozen=True, slots=True)
class ForecastDistribution:
    """워크포워드 백테스트에서 수집한 방향별 실현 수익률 분포.

    BacktestReport(적중 카운트)와 달리 수익률 원분포를 담아 확률·예측 밴드의 재료가 된다.
    감성은 중립 고정(과거 뉴스 수집 불가) — 지표 신호 기준이다.
    by_regime은 레짐 배열이 주입됐을 때만 채워진다(레짐 미상 평가일은 무조건부에만 반영).
    """

    horizon_days: int
    evaluated: int                          # veto 제외 후 평가일 수
    baseline_up_rate: float                 # 항상-UP 기준선(무조건부 상승 비율)
    by_direction: dict[str, DirectionStats]  # "UP" | "DOWN" | "NEUTRAL"
    by_regime: dict[str, RegimeStats] = field(default_factory=dict)  # BULL | BEAR | HIGH_VOL
    vetoed: int = 0                         # 어닝 등으로 평가에서 제외된 날 수
