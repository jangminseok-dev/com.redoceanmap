from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ForecastCaptureOutcome:
    captured: int          # 신규 저장 건수(중복 제외)
    skipped: list[str]     # 미수집·봉 부족으로 건너뛴 티커
    as_of: datetime | None = None  # 캡처가 본 최신 봉 기준일 — 모의투자 step의 날짜 축(신규 0건이어도 채움)


@dataclass(frozen=True)
class ForecastScoreOutcome:
    scored: int    # 이번 실행에서 채점 완료
    pending: int   # horizon 미도래로 남은 건수


@dataclass(frozen=True)
class AccuracyKpi:
    total: int
    scored: int
    pending: int
    hit_rate: float | None       # UP/DOWN 채점분 전체(NEUTRAL 제외)
    up_hit_rate: float | None
    down_hit_rate: float | None


@dataclass(frozen=True)
class HorizonStat:
    horizon_days: int
    scored: int
    hit_rate: float | None
    avg_realized_return_pct: float | None


@dataclass(frozen=True)
class DirectionStat:
    direction: str
    scored: int
    hit_rate: float | None
    avg_realized_return_pct: float | None


@dataclass(frozen=True)
class RegimeStat:
    """캡처 시점 시장 레짐(BULL/BEAR/HIGH_VOL)별 채점 성적 — 미상은 'NONE'."""

    regime: str
    scored: int
    hit_rate: float | None
    avg_realized_return_pct: float | None


@dataclass(frozen=True)
class SignalStat:
    """신호별 방향 일치율 — 원신호(signal) 부호와 실현 수익률 부호의 일치."""

    key: str
    n: int
    hits: int
    hit_rate: float | None


@dataclass(frozen=True)
class SnapshotInfo:
    """최근 스냅샷 1행 — 어드민 목록·CSV용."""

    ticker: str
    as_of: datetime
    horizon_days: int
    direction: str
    base_price: float
    score: float
    up_rate: float | None
    ready: bool
    evaluated_at: datetime | None
    realized_return_pct: float | None
    hit: bool | None
    regime: str | None = None
    earnings_veto: bool = False


@dataclass(frozen=True)
class ForecastAccuracyReport:
    """예측 채점 현황 리포트 — 어드민 페이지 1회 호출용 단일 문서."""

    kpi: AccuracyKpi
    by_horizon: list[HorizonStat]
    by_direction: list[DirectionStat]
    by_regime: list[RegimeStat]
    by_signal: list[SignalStat]
    recent: list[SnapshotInfo]
