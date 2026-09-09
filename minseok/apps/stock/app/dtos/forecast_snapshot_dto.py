from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CaptureCommand:
    """스냅샷 캡처 입력 — 워치리스트 티커 목록 × 평가 구간들."""

    tickers: list[str]
    horizons: list[int] = field(default_factory=lambda: [5])


@dataclass(frozen=True)
class CaptureResult:
    captured: int          # 신규 저장 건수(중복 제외)
    skipped: list[str]     # 미수집·봉 부족으로 건너뛴 티커
    # 이번 캡처가 본 스냅샷의 최신 봉 기준일. 모의투자 step이 같은 날짜 축으로 스냅샷을 찾도록
    # 배치 스크립트에 돌려준다 — 신규 저장 0건(주말·중복)이어도 채운다(금요일 세션 step의 멱등 재호출).
    as_of: datetime | None = None


@dataclass(frozen=True)
class ScoreResult:
    scored: int    # 이번 실행에서 채점 완료된 건수
    pending: int   # 아직 horizon 미도래로 남은 건수


@dataclass(frozen=True)
class SnapshotScoreUpdate:
    """채점 결과 1건 — 리포지토리 apply_scores 입력."""

    snapshot_id: int
    evaluated_at: datetime
    realized_price: float
    realized_return_pct: float
    hit: bool | None       # NEUTRAL은 None
    # 구간 내 실제 장중 최저 — 마감가만으로는 "얼마나 빠졌다 돌아왔나"를 알 수 없다.
    # 오답 분석의 핵심 필드(틀린 예측이 얼마나 나쁘게 틀렸는지). 봉에 저가가 없으면 None.
    realized_trough_pct: float | None = None


@dataclass(frozen=True)
class SummaryKpi:
    total: int
    scored: int
    pending: int
    hit_rate: float | None       # UP/DOWN 채점분 전체 적중률(NEUTRAL 제외)
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
    hit_rate: float | None       # NEUTRAL은 None
    avg_realized_return_pct: float | None


@dataclass(frozen=True)
class RegimeStat:
    """캡처 시점 레짐별 채점 성적 — 레짐 미상(지수 미수집 시기)은 'NONE' 그룹."""

    regime: str
    scored: int
    hit_rate: float | None
    avg_realized_return_pct: float | None


@dataclass(frozen=True)
class SignalStat:
    """신호별 방향 일치율 — signal 부호와 실현 수익률 부호의 일치(가중치 무관, 원신호 기준)."""

    key: str
    n: int         # signal != 0 인 채점 표본 수
    hits: int
    hit_rate: float | None


@dataclass(frozen=True)
class SnapshotRow:
    """최근 스냅샷 목록 1행 — 어드민 테이블용."""

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
class SnapshotSummaryView:
    kpi: SummaryKpi
    by_horizon: list[HorizonStat]
    by_direction: list[DirectionStat]
    by_regime: list[RegimeStat]
    by_signal: list[SignalStat]
    recent: list[SnapshotRow]
