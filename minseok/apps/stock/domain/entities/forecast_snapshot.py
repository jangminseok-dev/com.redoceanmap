from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from stock.domain.value_objects.signal_breakdown import SignalContribution

DIRECTIONS = ("UP", "DOWN", "NEUTRAL")


@dataclass(frozen=True)
class ForecastSnapshot:
    """예측 스냅샷 1건 — forecast 응답 + 신호 분해를 저장 시점 그대로 동결한 기록.

    (ticker, horizon_days, as_of)가 자연 유니크 키. 채점 필드(evaluated_*·hit)는
    horizon 도래 후 채워진다. hit: UP→상승 적중, DOWN→비상승 적중, NEUTRAL→None
    (방향 주장이 아니므로 적중률 분모에서 제외 — Backtester 의미론과 동일).
    """

    ticker: str              # 저장 티커 정본(resolved_ticker)
    as_of: datetime          # 마지막 봉 시각(UTC)
    horizon_days: int
    direction: str           # UP | DOWN | NEUTRAL
    base_price: float
    score: float             # OutlookPredictor.score(breakdown) 합산 점수
    signals: tuple[SignalContribution, ...]
    up_rate: float | None = None
    sample_size: int | None = None
    hits: int | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    baseline_up_rate: float | None = None
    ready: bool = False
    band_source: str | None = None
    q25_pct: float | None = None
    median_pct: float | None = None
    q75_pct: float | None = None
    # --- 판정 재현·재적합용 (2026-07-30) ---
    # signal_config: 어느 가중치 조합으로 낸 판정인가. NULL = 2026-07-30 이전의 default() 조합
    # (감성 가중치가 사장돼 전량 NEUTRAL이던 구간) — 이력이 조용히 섞이지 않게 표시한다.
    signal_config: str | None = None
    rsi: float | None = None            # 원시값 — signals에는 정규화 신호만 남아 복원 불가
    bb_percent_b: float | None = None
    momentum_12_1: float | None = None
    atr_pct: float | None = None
    drawdown_from_high_pct: float | None = None  # 캡처 시점 60일 고점 대비
    above_support_pct: float | None = None
    # --- 하방·회복 기대치(캡처 시점 백테스트 분포) ---
    trough_median_pct: float | None = None
    trough_q25_pct: float | None = None
    recovery_rate: float | None = None
    recovery_days_median: float | None = None
    evaluated_at: datetime | None = None
    realized_price: float | None = None
    realized_return_pct: float | None = None
    # 실제 구간 내 장중 최저 — "틀렸을 때 얼마나 빠졌나"의 답이 되는 채점 필드
    realized_trough_pct: float | None = None
    hit: bool | None = None
    regime: str | None = None         # 캡처 시점 시장 레짐(BULL/BEAR/HIGH_VOL)
    regime_conditional: bool = False  # 확률·밴드가 레짐 조건부 통계였는지
    earnings_veto: bool = False       # 실적 ±2일 관망 강등 여부
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.ticker:
            raise ValueError("ForecastSnapshot은 ticker가 필수입니다.")
        if self.direction not in DIRECTIONS:
            raise ValueError(f"direction은 {DIRECTIONS} 중 하나여야 합니다: {self.direction}")
        if self.horizon_days <= 0:
            raise ValueError(f"horizon_days는 양수여야 합니다: {self.horizon_days}")
