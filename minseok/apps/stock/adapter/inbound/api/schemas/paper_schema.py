"""모의투자 응답 스키마 — 백엔드 DTO 필드명을 그대로 쓴다(snake_case, 프론트 변환 금지)."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class PaperMyselfResponse(BaseModel):
    name: str
    description: str
    endpoints: list[str]
    rules: dict


class BoardRowSchema(BaseModel):
    key: str
    kind: str
    label: str
    equity_krw: float
    return_pct: float
    open_positions: int
    trades: int
    last_as_of: date | None


class BenchmarkPointSchema(BaseModel):
    as_of: date
    equity_krw: float


class PaperBoardResponse(BaseModel):
    rows: list[BoardRowSchema]
    spy: list[BenchmarkPointSchema]
    replay_until: date | None
    rules: dict


class PositionSchema(BaseModel):
    ticker: str
    name: str
    side: str
    quantity: int
    avg_price: float
    last_price: float | None
    unrealized_pct: float | None
    value_krw: float
    opened_at: datetime


class EquityPointSchema(BaseModel):
    as_of: date
    cash_krw: float
    positions_value_krw: float
    equity_krw: float
    replayed: bool


class TradeSchema(BaseModel):
    id: int
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


class PaperAccountResponse(BaseModel):
    key: str
    kind: str
    label: str
    cash_krw: float
    equity_krw: float
    initial_cash_krw: float
    started_on: date
    positions: list[PositionSchema]
    equity: list[EquityPointSchema]
    trades: list[TradeSchema]


class ScoreSchema(BaseModel):
    ticker: str
    action: str
    reason_kind: str
    realized_return_pct: float
    hit: bool


class DecisionSchema(BaseModel):
    id: int
    as_of: datetime
    market_view: str
    orders: list[dict]
    rejected: list[dict]
    candidates: list[dict]
    fills: list[TradeSchema]
    scores: list[ScoreSchema]
    replayed: bool
    latency_ms: int


class PaperDecisionsResponse(BaseModel):
    key: str
    decisions: list[DecisionSchema]


class ScoreBucketSchema(BaseModel):
    key: str
    n: int
    hits: int
    hit_rate: float | None = Field(description="표본이 min_samples 미만이면 null — 숫자를 노출하지 않는다")
    ci_low: float | None
    ci_high: float | None


class PaperScorecardResponse(BaseModel):
    key: str
    total: ScoreBucketSchema
    by_reason: list[ScoreBucketSchema]
    by_action: list[ScoreBucketSchema]
    min_samples: int


class PlaceOrderRequest(BaseModel):
    ticker: str
    action: str = Field(description="BUY | SELL | SHORT | COVER")
    quantity: int = Field(ge=1)


class OrderReceiptSchema(BaseModel):
    ticker: str
    action: str
    quantity: int
    price: float
    fee_krw: float
    realized_pnl_krw: float | None
    cash_krw: float
    price_as_of: datetime
