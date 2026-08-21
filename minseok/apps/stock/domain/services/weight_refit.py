"""가중치 재적합 — 동결 원신호 × 실현 수익률로 판정 조합 후보를 재채점하고 승격을 판정한다.

스냅샷 `signals`에는 6개 정규화 원신호가 config 무관하게 동결돼 있어, 임의 가중치
조합의 성적을 DB 표본만으로 재계산할 수 있다(백테스트 재실행 불요). 저장된 `hit`은
쓰지 않는다 — 옛 direction 기준 채점이라 후보 조합의 판정과 무관하다. 재판정은
`realized_return_pct > 0`으로 한다(Backtester UP 적중 의미론과 동일).

후보는 명시 열거 ~32조합(재채점 2·3차 관례 — 조합 폭발·다중 비교 억제):
5신호 가중치 대표 조합 × up_threshold 4종. `w_sentiment=0` 고정(스냅샷 경로는 감성
중립이라 sentiment 원신호가 항상 0 — 감성 재적합은 ROADMAP E3의 몫),
`down_threshold=-1.01` 고정(하락 무발화 정책 — 재채점 2·3차 모두 하락 방향은 두 구간
연속 통과 조합이 없었다), atr_veto·volume_confirm 스윕 없음(기각된 손잡이 +
volume_ratio 미저장).

승격 게이트(전부 gate_horizon 표본 기준):
  ① n ≥ MIN_SIGNAL_SAMPLES(100) AND Wilson 95% 하한 > 기준선(표본 전체 상승 비율)
  ② 후보 하한 ≥ 현행 조합 재채점 하한 + PROMOTION_MARGIN(히스테리시스 — 승격 진동 방지)
  ③ 승자 파라미터 ≠ 현행 파라미터(멱등 — 같은 날 재실행이 재승격하지 않는다)

payload 스키마의 단일 정의처는 `RefitReport.to_payload()`다(event_study 선례).
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.value_objects.backtest_report import MIN_SIGNAL_SAMPLES, wilson_lower_bound

PROMOTION_MARGIN = 0.02   # 현행 대비 Wilson 하한 개선 최소폭 — 승격 히스테리시스
DOWN_THRESHOLD = -1.01    # 하락 무발화 고정(score는 [-1,1] 클램프라 도달 불가)

# (w_rsi, w_trend, w_bb, w_obv, w_momentum) — 합 1.0 대표 조합 명시 열거
_WEIGHT_SETS: tuple[tuple[float, float, float, float, float], ...] = (
    (0.40, 0.00, 0.40, 0.00, 0.20),  # 현행 시드(3차 재채점 최우수 RSI+BB+MOM)
    (0.50, 0.00, 0.50, 0.00, 0.00),  # 2차 재채점 검증 조합(RSI+BB)
    (0.50, 0.00, 0.30, 0.00, 0.20),
    (0.30, 0.00, 0.50, 0.00, 0.20),
    (0.35, 0.00, 0.35, 0.00, 0.30),
    (0.40, 0.20, 0.40, 0.00, 0.00),
    (0.30, 0.00, 0.30, 0.20, 0.20),
    (0.25, 0.25, 0.25, 0.00, 0.25),
)
_UP_THRESHOLDS: tuple[float, ...] = (0.25, 0.30, 0.35, 0.40)


@dataclass(frozen=True)
class RefitSample:
    """재적합 표본 1건 — 동결 원신호(key → signal)와 실현 수익률."""

    signals: Mapping[str, float]
    realized_return_pct: float


@dataclass(frozen=True)
class CandidateResult:
    """후보 조합 1개의 재채점 성적."""

    up_threshold: float
    w_rsi: float
    w_trend: float
    w_bb: float
    w_obv: float
    w_momentum: float
    n: int                    # UP 판정 표본 수
    hits: int                 # 그중 실현 수익률 > 0
    hit_rate: float | None
    wilson_lower: float
    is_current: bool
    gate_passed: bool         # 게이트 ①(n·Wilson>기준선)만 — ②③은 리포트 수준 판정

    def params(self) -> tuple[float, ...]:
        return (
            self.up_threshold, self.w_rsi, self.w_trend,
            self.w_bb, self.w_obv, self.w_momentum,
        )


@dataclass(frozen=True)
class HorizonBoard:
    """지평 하나의 리더보드 — Wilson 하한 내림차순."""

    horizon_days: int
    total: int                # (veto 제외 후) 채점 표본 수
    baseline_up_rate: float   # 표본 전체 상승 비율 — 비교 기준선
    current: CandidateResult | None   # 현행 조합 재채점(표본 0이면 None)
    rows: list[CandidateResult]


@dataclass(frozen=True)
class RefitReport:
    """재적합 실행 1회의 결과 — 승격 판정 + 지평별 리더보드."""

    gate_horizon: int
    boards: list[HorizonBoard]        # gate_horizon 먼저, 나머지는 참고 병기
    promote: bool
    winner: CandidateResult | None    # promote=True일 때 승격 대상(게이트 통과 최상위)
    reasons: list[str]                # 판정 사유 — 미달이어도 "왜"를 남긴다

    def winner_config(self) -> AnalysisConfig | None:
        if self.winner is None:
            return None
        w = self.winner
        return AnalysisConfig(
            up_threshold=w.up_threshold, down_threshold=DOWN_THRESHOLD,
            w_sentiment=0.0, w_rsi=w.w_rsi, w_trend=w.w_trend,
            w_bb=w.w_bb, w_obv=w.w_obv, w_momentum=w.w_momentum,
        )

    def to_payload(self) -> dict:
        """리포트 payload 스키마의 단일 정의처 — 영속·어드민 매핑이 이 키를 따른다."""
        return {
            "gate_horizon": self.gate_horizon,
            "promote": self.promote,
            "winner": _candidate_payload(self.winner) if self.winner else None,
            "reasons": list(self.reasons),
            "boards": [
                {
                    "horizon_days": b.horizon_days,
                    "total": b.total,
                    "baseline_up_rate": b.baseline_up_rate,
                    "current": _candidate_payload(b.current) if b.current else None,
                    "rows": [_candidate_payload(r) for r in b.rows],
                }
                for b in self.boards
            ],
        }


def _candidate_payload(c: CandidateResult) -> dict:
    return {
        "up_threshold": c.up_threshold,
        "w_rsi": c.w_rsi, "w_trend": c.w_trend, "w_bb": c.w_bb,
        "w_obv": c.w_obv, "w_momentum": c.w_momentum,
        "n": c.n, "hits": c.hits, "hit_rate": c.hit_rate,
        "wilson_lower": c.wilson_lower,
        "is_current": c.is_current, "gate_passed": c.gate_passed,
    }


def refit(
    samples_by_horizon: Mapping[int, Sequence[RefitSample]],
    current: AnalysisConfig,
    gate_horizon: int = 5,
) -> RefitReport:
    """지평별 표본으로 후보 전량을 재채점하고 gate_horizon 기준으로 승격을 판정한다."""
    current_params = (
        current.up_threshold, current.w_rsi, current.w_trend,
        current.w_bb, current.w_obv, current.w_momentum,
    )
    boards = [
        _board(horizon, samples_by_horizon.get(horizon, ()), current, current_params)
        for horizon in sorted(samples_by_horizon, key=lambda h: (h != gate_horizon, h))
    ]

    gate_board = next((b for b in boards if b.horizon_days == gate_horizon), None)
    promote, winner, reasons = _judge(gate_board, gate_horizon)
    return RefitReport(
        gate_horizon=gate_horizon, boards=boards,
        promote=promote, winner=winner, reasons=reasons,
    )


def _judge(
    board: HorizonBoard | None, gate_horizon: int
) -> tuple[bool, CandidateResult | None, list[str]]:
    if board is None or board.total == 0:
        return False, None, [f"게이트 지평({gate_horizon}일) 채점 표본이 없습니다."]

    passed = [r for r in board.rows if r.gate_passed]
    if not passed:
        return False, None, [
            f"게이트 통과 후보 0개 — n≥{MIN_SIGNAL_SAMPLES} + Wilson 하한 > "
            f"기준선({board.baseline_up_rate:.3f})을 만족한 조합이 없습니다"
            f"(표본 {board.total}건).",
        ]

    winner = passed[0]  # rows는 이미 Wilson 하한 내림차순
    current_lower = board.current.wilson_lower if board.current else 0.0
    if winner.is_current:
        return False, winner, [
            "최상위 후보가 현행 조합과 동일합니다 — 변경 없음(멱등).",
        ]
    if winner.wilson_lower < current_lower + PROMOTION_MARGIN:
        return False, winner, [
            f"최상위 후보 하한({winner.wilson_lower:.3f})이 현행 재채점 하한"
            f"({current_lower:.3f}) + 마진({PROMOTION_MARGIN})에 못 미칩니다 — 승격 보류.",
        ]
    return True, winner, [
        f"게이트 통과: n={winner.n}, 하한 {winner.wilson_lower:.3f} > "
        f"기준선 {board.baseline_up_rate:.3f}, 현행 대비 +"
        f"{winner.wilson_lower - current_lower:.3f} ≥ 마진 {PROMOTION_MARGIN}.",
    ]


def _board(
    horizon: int,
    samples: Sequence[RefitSample],
    current: AnalysisConfig,
    current_params: tuple[float, ...],
) -> HorizonBoard:
    baseline = (
        sum(1 for s in samples if s.realized_return_pct > 0) / len(samples)
        if samples else 0.0
    )
    rows = [
        _evaluate(samples, baseline, threshold, weights, current_params)
        for weights in _WEIGHT_SETS
        for threshold in _UP_THRESHOLDS
    ]
    # 현행 조합이 후보 열거 밖일 수 있다(과거 승격분) — 별도 재채점해 비교 기준으로 쓴다
    current_row = _evaluate(
        samples, baseline, current.up_threshold,
        (current.w_rsi, current.w_trend, current.w_bb, current.w_obv, current.w_momentum),
        current_params,
    )
    rows.sort(key=lambda r: (-r.wilson_lower, -r.n, r.up_threshold))
    return HorizonBoard(
        horizon_days=horizon, total=len(samples), baseline_up_rate=baseline,
        current=current_row if samples else None, rows=rows,
    )


def _evaluate(
    samples: Sequence[RefitSample],
    baseline: float,
    up_threshold: float,
    weights: tuple[float, float, float, float, float],
    current_params: tuple[float, ...],
) -> CandidateResult:
    w_rsi, w_trend, w_bb, w_obv, w_momentum = weights
    n = hits = 0
    for s in samples:
        # OutlookPredictor.score와 같은 합산·클램프 — sentiment는 스냅샷 경로에서 항상 0
        score = (
            w_rsi * s.signals.get("rsi", 0.0)
            + w_trend * s.signals.get("trend", 0.0)
            + w_bb * s.signals.get("bollinger", 0.0)
            + w_obv * s.signals.get("obv", 0.0)
            + w_momentum * s.signals.get("momentum", 0.0)
        )
        score = max(-1.0, min(1.0, score))
        if score >= up_threshold:
            n += 1
            if s.realized_return_pct > 0:
                hits += 1
    lower = wilson_lower_bound(hits, n)
    params = (up_threshold, *weights)
    return CandidateResult(
        up_threshold=up_threshold,
        w_rsi=w_rsi, w_trend=w_trend, w_bb=w_bb, w_obv=w_obv, w_momentum=w_momentum,
        n=n, hits=hits, hit_rate=hits / n if n else None,
        wilson_lower=lower,
        is_current=all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(params, current_params)),
        gate_passed=n >= MIN_SIGNAL_SAMPLES and lower > baseline,
    )
