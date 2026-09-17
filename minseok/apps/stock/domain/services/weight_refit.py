"""가중치 재적합 — 동결 원신호 × 실현 수익률로 판정 조합 후보를 재채점하고 승격을 판정한다.

스냅샷 `signals`에는 6개 정규화 원신호가 config 무관하게 동결돼 있어, 임의 가중치
조합의 성적을 DB 표본만으로 재계산할 수 있다(백테스트 재실행 불요). 저장된 `hit`은
쓰지 않는다 — 옛 direction 기준 채점이라 후보 조합의 판정과 무관하다. 재판정은
`is_up_hit(realized_return_pct, ATR% × √horizon)`으로 한다(Backtester UP 적중 의미론과
동일 — 2026-08-28 [1]-①로 부호 판정에서 변동성 초과 판정으로 함께 바뀌었다. 두 곳이
갈라지면 재적합이 백테스트와 다른 기준으로 승격을 결정하게 된다).

후보는 명시 열거 ~32조합(재채점 2·3차 관례 — 조합 폭발·다중 비교 억제):
5신호 가중치 대표 조합 × up_threshold 4종. `w_sentiment=0` 고정(스냅샷 경로는 감성
중립이라 sentiment 원신호가 항상 0 — 감성 재적합은 ROADMAP E3의 몫),
`down_threshold=-1.01` 고정(하락 무발화 — 2026-09-17 81종목 10년 재검증에서 뒤 5년 미달, AnalysisConfig.forecast_signal
docstring 참조. 상승 가중치만 스윕한다), atr_veto·volume_confirm 스윕 없음(기각된 손잡이 +
volume_ratio 미저장).

승격 게이트(전부 gate_horizon 표본 기준, 2026-09-17 개정):
  0) 표본을 **선택 구간**(최신 as_of로부터 HOLDOUT_DAYS일 이전)과 **표본 외 구간**(최신 HOLDOUT_DAYS일)으로 가른다 —
     9/1 승격은 7/20~8/31 상승장 표본 안에서만 골라 9월에 무너졌다(상승 적중 51.9% → 17.8%).
     n·적중률·Wilson은 **실효 표본**(같은 종목·같은 ISO 주의 신호를 1군집으로 묶어 군집 평균)으로 센다 —
     상승 신호의 45%가 같은 종목 3일 내 반복이라 원표본 수로는 신뢰구간이 부풀었다.
  ① n ≥ MIN_SIGNAL_SAMPLES(100) AND Wilson 95% 하한 > 기준선
     (기준선은 후보가 신호를 낸 **종목들의 자기 기준선을 신호 수로 가중**한 값 —
      2026-08-28 [1]-③. 표본 전체 pooled 값을 쓰면 신호를 안 낸 종목이 섞여 왜곡된다)
  ② 후보 하한 ≥ 현행 조합 재채점 하한 + PROMOTION_MARGIN(히스테리시스 — 승격 진동 방지)
  ③ 승자 파라미터 ≠ 현행 파라미터(멱등 — 같은 날 재실행이 재승격하지 않는다)
  ④ 승자가 표본 외 구간에서도 실효 표본 ≥ MIN_HOLDOUT_EFFECTIVE이고 실효 적중률 > 그 구간 종목 기준선
     (날짜 없는 표본이면 표본 외 검증 불가 — 승격하지 않는다)

payload 스키마의 단일 정의처는 `RefitReport.to_payload()`다(event_study 선례).
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.value_objects.backtest_report import (
    MIN_SIGNAL_SAMPLES,
    hit_unit,
    is_up_hit,
    wilson_lower_bound,
)

PROMOTION_MARGIN = 0.02   # 현행 대비 Wilson 하한 개선 최소폭 — 승격 히스테리시스
DOWN_THRESHOLD = -1.01    # 하락 무발화(2026-09-17 재검증 미달) — AnalysisConfig.forecast_signal 참조
HOLDOUT_DAYS = 14         # 선택에 쓰지 않는 최신 구간(달력일)
MIN_HOLDOUT_EFFECTIVE = 20  # 표본 외 구간 최소 실효 표본(종목×ISO 주 군집)

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
    """재적합 표본 1건 — 동결 원신호(key → signal)와 실현 수익률.

    ticker·atr_pct는 적중 판정과 종목별 기준선에 쓴다. atr_pct가 없는 옛 스냅샷은
    `hit_unit`이 0을 돌려 부호 판정으로 열화한다(표본에서 빼지 않는다).
    """

    signals: Mapping[str, float]
    realized_return_pct: float
    ticker: str
    atr_pct: float | None
    as_of: datetime | None = None  # 실효 표본 군집(종목×ISO 주)·표본 외 구간 분할 — 없으면 표본마다 따로 센다


@dataclass(frozen=True)
class CandidateResult:
    """후보 조합 1개의 재채점 성적."""

    up_threshold: float
    w_rsi: float
    w_trend: float
    w_bb: float
    w_obv: float
    w_momentum: float
    n: int                    # UP 판정 원표본 수
    hits: int                 # 그중 적중(변동성 초과 상승)
    hit_rate: float | None    # 실효 적중률(군집 평균의 평균) — 게이트가 쓰는 값
    baseline: float           # 이 후보가 신호를 낸 군집들의 종목 기준선 평균
    wilson_lower: float       # 실효 표본 기준 Wilson 95% 하한
    is_current: bool
    gate_passed: bool         # 게이트 ①(실효 n·Wilson>기준선)만 — ②③④는 리포트 수준 판정
    n_effective: int = 0      # 종목×ISO 주 군집 수

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
    winner_holdout: CandidateResult | None = None  # 승자의 표본 외 구간 재채점(없으면 검증 불가)

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
            "holdout_days": HOLDOUT_DAYS,
            "winner_holdout": _candidate_payload(self.winner_holdout) if self.winner_holdout else None,
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
        "n": c.n, "n_effective": c.n_effective, "hits": c.hits, "hit_rate": c.hit_rate,
        "baseline": c.baseline,
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
    boards = []
    holdouts: dict[int, list[RefitSample]] = {}
    for horizon in sorted(samples_by_horizon, key=lambda h: (h != gate_horizon, h)):
        selection, holdouts[horizon] = split_holdout(samples_by_horizon.get(horizon, ()))
        boards.append(_board(horizon, selection, current, current_params))

    gate_board = next((b for b in boards if b.horizon_days == gate_horizon), None)
    promote, winner, reasons = _judge(gate_board, gate_horizon)
    winner_holdout = None
    if winner is not None and not winner.is_current:
        held = holdouts.get(gate_horizon, [])
        if held:
            winner_holdout = _evaluate(
                _scored(gate_horizon, held), winner.up_threshold,
                (winner.w_rsi, winner.w_trend, winner.w_bb, winner.w_obv, winner.w_momentum), current_params,
            )
        if promote:
            promote, reasons = _judge_holdout(winner_holdout, reasons)
    return RefitReport(
        gate_horizon=gate_horizon, boards=boards,
        promote=promote, winner=winner, reasons=reasons, winner_holdout=winner_holdout,
    )


def split_holdout(samples: Sequence[RefitSample]) -> tuple[list[RefitSample], list[RefitSample]]:
    """최신 as_of로부터 HOLDOUT_DAYS일 안쪽은 표본 외 구간 — 날짜 없는 표본이 섞이면 분할하지 않는다."""
    if not samples or any(s.as_of is None for s in samples):
        return list(samples), []
    cutoff = max(s.as_of for s in samples) - timedelta(days=HOLDOUT_DAYS)
    return [s for s in samples if s.as_of <= cutoff], [s for s in samples if s.as_of > cutoff]


def _judge_holdout(holdout: CandidateResult | None, reasons: list[str]) -> tuple[bool, list[str]]:
    if holdout is None:
        return False, [f"표본 외 검증 불가 — 최근 {HOLDOUT_DAYS}일 표본이 없거나 날짜가 없습니다. 승격 보류.", *reasons]
    if holdout.n_effective < MIN_HOLDOUT_EFFECTIVE:
        return False, [f"표본 외(최근 {HOLDOUT_DAYS}일) 실효 표본 {holdout.n_effective} < {MIN_HOLDOUT_EFFECTIVE} — 승격 보류.", *reasons]
    if holdout.hit_rate is None or holdout.hit_rate <= holdout.baseline:
        rate = f"{holdout.hit_rate:.3f}" if holdout.hit_rate is not None else "없음"
        return False, [f"표본 외(최근 {HOLDOUT_DAYS}일) 적중 {rate} ≤ 기준선 {holdout.baseline:.3f} — 승격 보류.", *reasons]
    return True, [*reasons, f"표본 외(최근 {HOLDOUT_DAYS}일) 통과: 실효 n={holdout.n_effective}, 적중 {holdout.hit_rate:.3f} > 기준선 {holdout.baseline:.3f}."]


def _judge(
    board: HorizonBoard | None, gate_horizon: int
) -> tuple[bool, CandidateResult | None, list[str]]:
    if board is None or board.total == 0:
        return False, None, [f"게이트 지평({gate_horizon}일) 채점 표본이 없습니다."]

    passed = [r for r in board.rows if r.gate_passed]
    if not passed:
        return False, None, [
            f"게이트 통과 후보 0개 — n≥{MIN_SIGNAL_SAMPLES} + Wilson 하한 > "
            f"종목 가중 기준선(표본 전체 {board.baseline_up_rate:.3f})을 만족한 조합이 없습니다"
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
        f"기준선 {winner.baseline:.3f}, 현행 대비 +"
        f"{winner.wilson_lower - current_lower:.3f} ≥ 마진 {PROMOTION_MARGIN}.",
    ]


@dataclass(frozen=True)
class _Scored:
    """표본 1건을 채점해 둔 것 — 적중 여부와 그 종목의 기준선을 미리 붙인다."""

    sample: RefitSample
    hit: bool
    ticker_baseline: float


def _scored(horizon: int, samples: Sequence[RefitSample]) -> list[_Scored]:
    """적중 판정(변동성 초과) + 종목별 기준선을 한 번만 계산한다."""
    hits = [
        (s, is_up_hit(s.realized_return_pct, hit_unit(s.atr_pct, horizon)))
        for s in samples
    ]
    by_ticker: dict[str, list[bool]] = {}
    for s, hit in hits:
        by_ticker.setdefault(s.ticker, []).append(hit)
    baselines = {t: sum(rows) / len(rows) for t, rows in by_ticker.items()}
    return [_Scored(s, hit, baselines[s.ticker]) for s, hit in hits]


def _board(
    horizon: int,
    samples: Sequence[RefitSample],
    current: AnalysisConfig,
    current_params: tuple[float, ...],
) -> HorizonBoard:
    scored = _scored(horizon, samples)
    # 보드 기준선은 표시용 pooled 값 — 게이트는 후보별 가중 기준선(CandidateResult.baseline)을 쓴다
    baseline = sum(1 for r in scored if r.hit) / len(scored) if scored else 0.0
    rows = [
        _evaluate(scored, threshold, weights, current_params)
        for weights in _WEIGHT_SETS
        for threshold in _UP_THRESHOLDS
    ]
    # 현행 조합이 후보 열거 밖일 수 있다(과거 승격분) — 별도 재채점해 비교 기준으로 쓴다
    current_row = _evaluate(
        scored, current.up_threshold,
        (current.w_rsi, current.w_trend, current.w_bb, current.w_obv, current.w_momentum),
        current_params,
    )
    rows.sort(key=lambda r: (-r.wilson_lower, -r.n_effective, r.up_threshold))
    return HorizonBoard(
        horizon_days=horizon, total=len(samples), baseline_up_rate=baseline,
        current=current_row if samples else None, rows=rows,
    )


def _evaluate(
    scored: Sequence[_Scored],
    up_threshold: float,
    weights: tuple[float, float, float, float, float],
    current_params: tuple[float, ...],
) -> CandidateResult:
    w_rsi, w_trend, w_bb, w_obv, w_momentum = weights
    n = hits = 0
    clusters: dict[tuple, list[_Scored]] = {}
    for i, row in enumerate(scored):
        s = row.sample
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
            if row.hit:
                hits += 1
            clusters.setdefault(_cluster_key(s, i), []).append(row)
    # 실효 표본 — 군집마다 적중률·종목 기준선을 평균낸 뒤 군집을 1건으로 센다.
    # 후보가 실제로 신호를 낸 종목 구성으로 기준선을 만든다 — 신호를 안 낸 종목은 안 섞인다
    n_eff = len(clusters)
    eff_hits = sum(sum(r.hit for r in rows) / len(rows) for rows in clusters.values())
    baseline = sum(rows[0].ticker_baseline for rows in clusters.values()) / n_eff if n_eff else 0.0
    lower = wilson_lower_bound(eff_hits, n_eff)
    params = (up_threshold, *weights)
    return CandidateResult(
        up_threshold=up_threshold,
        w_rsi=w_rsi, w_trend=w_trend, w_bb=w_bb, w_obv=w_obv, w_momentum=w_momentum,
        n=n, hits=hits, hit_rate=eff_hits / n_eff if n_eff else None,
        baseline=baseline,
        wilson_lower=lower,
        is_current=all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(params, current_params)),
        gate_passed=n_eff >= MIN_SIGNAL_SAMPLES and lower > baseline,
        n_effective=n_eff,
    )


def _cluster_key(sample: RefitSample, index: int) -> tuple:
    """같은 종목·같은 ISO 주는 한 군집 — 날짜가 없으면 표본마다 따로(옛 스냅샷·테스트 호환)."""
    if sample.as_of is None:
        return (sample.ticker, index)
    year, week, _ = sample.as_of.isocalendar()
    return (sample.ticker, year, week)
