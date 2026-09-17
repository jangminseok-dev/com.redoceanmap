from __future__ import annotations

from dataclasses import dataclass

# "확률 제시 가능" 판정 기준(로드맵 ①-M2에서 명문화):
# 방향별 신호 표본이 최소 이만큼 쌓이고, Wilson 95% 신뢰구간 하한이 기준선을 넘어야 한다.
MIN_SIGNAL_SAMPLES = 100
WILSON_Z = 1.96  # 95%

# 적중 판정 문턱(2026-08-28 [1]-① 정의 변경) — 실현 수익률이 변동성 1단위
# (ATR% × √horizon)의 이만큼을 넘어야 적중이다. 부호(> 0)만 보면 잡음 수준의 +0.01%도
# 적중이 되고, 변동성이 큰 종목일수록 우연한 통과가 쉬워 종목 간 비교가 왜곡된다.
HIT_Z_MIN = 0.25


def hit_unit(atr_pct: float | None, horizon_days: int) -> float:
    """변동성 1단위 = ATR% × √horizon.

    ATR을 모르는 표본(옛 스냅샷 등)은 0을 돌려 부호 판정으로 열화한다 — 채점에서
    빼면 표본이 줄고, 임의값을 넣으면 없는 근거를 만든다.
    """
    if not atr_pct or atr_pct <= 0.0 or horizon_days <= 0:
        return 0.0
    return atr_pct * (horizon_days ** 0.5)


def is_up_hit(return_pct: float, unit: float, z_min: float = HIT_Z_MIN) -> bool:
    """상승 적중 — 수익률이 변동성 단위의 z_min배를 넘었는가."""
    return return_pct > unit * z_min


def is_down_hit(return_pct: float, unit: float, z_min: float = HIT_Z_MIN) -> bool:
    """하락 적중 — 대칭. 하락은 현행 정책상 무발화지만 정의는 같이 둔다."""
    return return_pct < -unit * z_min


def wilson_lower_bound(hits: int, n: int, z: float = WILSON_Z) -> float:
    """이항 비율의 Wilson score 신뢰구간 하한 — 소표본 낙관을 걸러낸다."""
    if n == 0:
        return 0.0
    p = hits / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return center - margin


def overlap_effective(hits: int, n: int, horizon_days: int) -> tuple[float, float]:
    """매일 평가한 horizon일 수익률은 창이 겹친다 — 독립 표본 수는 대략 n ÷ horizon(2026-09-17 점검).

    원표본으로 Wilson을 쓰면 구간이 √horizon배 좁아져 "통계적으로 유의"가 과하게 켜졌다(5일 지평이면 약 2.2배).
    펀더멘털 백테스트가 이미 쓰던 겹침 보정(n ÷ 지평)과 같은 규칙이다. (유효 적중, 유효 n)을 실수로 돌려준다.
    """
    k = max(horizon_days, 1)
    return hits / k, n / k


def wilson_bounds(hits: float, n: float, z: float = WILSON_Z) -> tuple[float, float]:
    """Wilson score 신뢰구간 (하한, 상한) — 확률 표시에 구간을 병기하기 위한 대칭 계산."""
    if n == 0:
        return 0.0, 1.0
    p = hits / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return center - margin, center + margin


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """방향 전망 백테스트 결과. 과거 뉴스는 없으므로 지표 신호만 채점한 값이다."""

    horizon_days: int      # 전망 평가 구간(거래일)
    evaluated: int         # 평가한 날 수
    up_signals: int
    down_signals: int
    neutral_signals: int
    up_hits: int           # UP 신호 중 실제 상승
    down_hits: int         # DOWN 신호 중 실제 하락
    baseline_up_rate: float  # 항상 UP이라 가정한 적중률(변동성 초과 상승 비율) — UP 비교 기준선
    # 하락 기준선은 (1 − baseline_up_rate)가 **아니다**. 변동성 문턱을 쓰면 결과가 셋
    # (초과 상승 / 초과 하락 / 잡음 구간)이라 두 기준선을 따로 세야 한다. 모르면 None —
    # 이때 down_probability_ready는 판정하지 않는다(없는 기준선으로 통과시키지 않는다).
    baseline_down_rate: float | None = None

    @property
    def hits(self) -> int:
        return self.up_hits + self.down_hits

    @property
    def actionable(self) -> int:
        """방향을 낸 신호 수 (NEUTRAL 제외)."""
        return self.up_signals + self.down_signals

    @property
    def hit_rate(self) -> float | None:
        """방향 신호의 적중률. 신호가 없으면 None."""
        return self.hits / self.actionable if self.actionable else None

    @property
    def up_hit_rate(self) -> float | None:
        """UP 신호 적중률 — baseline_up_rate와 비교해야 의미가 있다."""
        return self.up_hits / self.up_signals if self.up_signals else None

    @property
    def down_hit_rate(self) -> float | None:
        """DOWN 신호 적중률 — (1 - baseline_up_rate)와 비교해야 의미가 있다."""
        return self.down_hits / self.down_signals if self.down_signals else None

    @property
    def up_probability_ready(self) -> bool:
        """UP 신호를 '확률'로 제시해도 되는가 — 표본 n≥100 + Wilson 95% 하한 > 기준선."""
        return (
            self.up_signals >= MIN_SIGNAL_SAMPLES
            and wilson_lower_bound(self.up_hits, self.up_signals) > self.baseline_up_rate
        )

    @property
    def down_probability_ready(self) -> bool:
        """DOWN 신호를 '확률'로 제시해도 되는가 — 표본 n≥100 + Wilson 95% 하한 > 하락 기준선."""
        if self.baseline_down_rate is None:
            return False
        return (
            self.down_signals >= MIN_SIGNAL_SAMPLES
            and wilson_lower_bound(self.down_hits, self.down_signals) > self.baseline_down_rate
        )

    def merged(self, other: "BacktestReport") -> "BacktestReport":
        """다종목 집계 — 신호·적중 카운트를 합산하고 기준선은 평가일 가중 평균."""
        if self.horizon_days != other.horizon_days:
            raise ValueError("horizon이 다른 리포트는 합칠 수 없습니다.")
        total = self.evaluated + other.evaluated
        return BacktestReport(
            horizon_days=self.horizon_days,
            evaluated=total,
            up_signals=self.up_signals + other.up_signals,
            down_signals=self.down_signals + other.down_signals,
            neutral_signals=self.neutral_signals + other.neutral_signals,
            up_hits=self.up_hits + other.up_hits,
            down_hits=self.down_hits + other.down_hits,
            baseline_up_rate=_weighted_baseline(self, other, "up"),
            baseline_down_rate=_weighted_baseline(self, other, "down"),
        )


def _weighted_baseline(
    a: "BacktestReport", b: "BacktestReport", side: str,
) -> float | None:
    """다종목 기준선 — 평가일이 아니라 **그 방향의 신호 수**로 가중한다(2026-08-28 [1]-③).

    비교 대상은 "신호가 난 날"이므로, 신호를 거의 내지 않은 종목의 기준선이 긴 평가
    기간만으로 과대 반영되면 우위 판정이 왜곡된다. 해당 방향 신호가 양쪽 다 0이면
    가중치가 성립하지 않으니 평가일로 되돌린다.
    """
    va, vb = (
        (a.baseline_up_rate, b.baseline_up_rate) if side == "up"
        else (a.baseline_down_rate, b.baseline_down_rate)
    )
    if va is None or vb is None:
        return None
    w_a, w_b = (
        (a.up_signals, b.up_signals) if side == "up" else (a.down_signals, b.down_signals)
    )
    if w_a + w_b == 0:
        w_a, w_b = a.evaluated, b.evaluated
    return (va * w_a + vb * w_b) / (w_a + w_b)
