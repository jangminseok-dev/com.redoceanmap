from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RefitRunOutcome:
    """재적합 실행 1회 요약 — 자동화(cron) 응답용."""

    promoted: bool
    activated_key: str | None   # 승격 시 새 활성 조합 키(refit-YYYYMMDD)
    reasons: list[str]


@dataclass(frozen=True)
class RefitCandidateRow:
    """후보 조합 1개의 재채점 성적 — 리더보드 1행."""

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
    gate_passed: bool         # n≥100 + Wilson 하한 > 기준선


@dataclass(frozen=True)
class RefitHorizonBoard:
    """지평 하나의 리더보드 — Wilson 하한 내림차순."""

    horizon_days: int
    total: int
    baseline_up_rate: float
    current: RefitCandidateRow | None
    rows: list[RefitCandidateRow] = field(default_factory=list)


@dataclass(frozen=True)
class RefitReportInfo:
    """최신 재적합 리포트 — 어드민 화면 1회 호출용."""

    ran_at: datetime
    params: dict
    gate_horizon: int
    promote: bool
    winner: RefitCandidateRow | None
    reasons: list[str]
    boards: list[RefitHorizonBoard] = field(default_factory=list)


@dataclass(frozen=True)
class SignalConfigInfo:
    """판정 조합 이력 1행 — 활성 조합과 과거 승격분."""

    key: str
    is_active: bool
    source: str               # seed | refit
    up_threshold: float
    down_threshold: float
    w_sentiment: float
    w_rsi: float
    w_trend: float
    w_bb: float
    w_obv: float
    w_momentum: float
    created_at: datetime
    activated_at: datetime | None
