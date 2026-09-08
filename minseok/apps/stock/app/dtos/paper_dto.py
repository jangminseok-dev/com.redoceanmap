"""AI 모의투자 DTO — 리포지토리 읽기/쓰기 레코드와 화면 뷰."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from stock.domain.services.paper_ledger import Position

# ---- 리포지토리 레코드 -----------------------------------------------------


@dataclass(frozen=True)
class AccountRecord:
    id: int
    kind: str  # exaone | signal
    user_id: int | None
    cash_krw: float
    initial_cash_krw: float
    started_on: date
    positions: tuple[Position, ...]

    @property
    def key(self) -> str:
        return self.kind


@dataclass(frozen=True)
class DecisionDraft:
    account_id: int
    as_of: datetime
    model: str
    prompt: str
    response_raw: str
    market_view: str
    orders: list[dict]
    rejected: list[dict]
    candidates: list[dict]
    latency_ms: int
    replayed: bool


@dataclass(frozen=True)
class DecisionRecord:
    id: int
    account_id: int
    as_of: datetime
    model: str
    market_view: str
    orders: list[dict]
    rejected: list[dict]
    candidates: list[dict]
    latency_ms: int
    replayed: bool
    filled_at: datetime | None
    scored_at: datetime | None
    prompt: str = ""
    response_raw: str = ""


@dataclass(frozen=True)
class TradeDraft:
    account_id: int
    ticker: str
    side: str
    action: str
    quantity: int
    price: float
    fee_krw: float
    realized_pnl_krw: float | None
    ts: datetime
    decision_id: int | None
    reason: str | None
    evidence: dict | None
    replayed: bool


@dataclass(frozen=True)
class TradeRecord:
    id: int
    account_id: int
    ticker: str
    side: str
    action: str
    quantity: int
    price: float
    fee_krw: float
    realized_pnl_krw: float | None
    ts: datetime
    decision_id: int | None
    reason: str | None
    evidence: dict | None
    replayed: bool


@dataclass(frozen=True)
class EquityPoint:
    as_of: date
    cash_krw: float
    positions_value_krw: float
    equity_krw: float
    replayed: bool


@dataclass(frozen=True)
class ScoreDraft:
    decision_id: int
    ticker: str
    action: str
    reason_kind: str
    realized_return_pct: float
    hit: bool
    evaluated_at: datetime


@dataclass(frozen=True)
class ScoreRecord:
    decision_id: int
    as_of: datetime
    ticker: str
    action: str
    reason_kind: str
    realized_return_pct: float
    hit: bool


# ---- 시세·신호 피드 ----------------------------------------------------------


@dataclass(frozen=True)
class SnapshotFeedRow:
    ticker: str
    as_of: datetime
    direction: str
    score: float
    base_price: float
    up_rate: float | None
    baseline_up_rate: float | None
    ready: bool
    atr_pct: float | None
    regime: str | None
    earnings_veto: bool


@dataclass(frozen=True)
class NewsFeedRow:
    news_id: int
    title: str
    url: str
    published_at: datetime
    sentiment: float | None
    event_type: str | None


# ---- 커맨드·결과 ---------------------------------------------------------------


@dataclass(frozen=True)
class StepCommand:
    as_of: datetime  # 판단 기준 시각(UTC). 이 시각 이후 데이터는 보지 않는다
    replay: bool = False


@dataclass(frozen=True)
class StepResult:
    as_of: datetime
    skipped: str | None  # 스냅샷 없음 등 — 아무것도 하지 않은 이유
    filled: int
    decisions: int
    scored: int
    equity_rows: int


# ---- 화면 뷰 -------------------------------------------------------------------


@dataclass(frozen=True)
class BoardRow:
    key: str
    kind: str
    label: str
    equity_krw: float
    return_pct: float
    open_positions: int
    trades: int
    last_as_of: date | None


@dataclass(frozen=True)
class BenchmarkPoint:
    as_of: date
    equity_krw: float  # 초기 자본을 SPY에 넣고 들고 있었을 때


@dataclass(frozen=True)
class BoardView:
    rows: tuple[BoardRow, ...]
    spy: tuple[BenchmarkPoint, ...]
    replay_until: date | None
    rules: dict


@dataclass(frozen=True)
class PositionView:
    ticker: str
    name: str
    side: str
    quantity: int
    avg_price: float
    last_price: float | None
    unrealized_pct: float | None
    value_krw: float
    opened_at: datetime


@dataclass(frozen=True)
class AccountView:
    key: str
    kind: str
    label: str
    cash_krw: float
    equity_krw: float
    initial_cash_krw: float
    started_on: date
    positions: tuple[PositionView, ...]
    equity: tuple[EquityPoint, ...]
    trades: tuple[TradeRecord, ...]


@dataclass(frozen=True)
class DecisionView:
    id: int
    as_of: datetime
    market_view: str
    orders: list[dict]
    rejected: list[dict]
    candidates: list[dict]
    fills: tuple[TradeRecord, ...]
    replayed: bool
    latency_ms: int
    scores: tuple[ScoreRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScoreBucket:
    key: str
    n: int
    hits: int
    hit_rate: float | None
    ci_low: float | None
    ci_high: float | None


@dataclass(frozen=True)
class ScorecardView:
    total: ScoreBucket
    by_reason: tuple[ScoreBucket, ...]
    by_action: tuple[ScoreBucket, ...]
    baseline_up_rate: float | None  # 같은 기간 스냅샷 기준선(참고)
    min_samples: int
