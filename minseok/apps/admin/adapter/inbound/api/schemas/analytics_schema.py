from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AccuracyKpiSchema(BaseModel):
    total: int
    scored: int
    pending: int
    hit_rate: float | None
    up_hit_rate: float | None
    down_hit_rate: float | None


class HorizonStatSchema(BaseModel):
    horizon_days: int
    scored: int
    hit_rate: float | None
    avg_realized_return_pct: float | None


class DirectionStatSchema(BaseModel):
    direction: str
    scored: int
    hit_rate: float | None
    avg_realized_return_pct: float | None


class RegimeStatSchema(BaseModel):
    regime: str  # BULL | BEAR | HIGH_VOL | NONE(지수 미수집 시기)
    scored: int
    hit_rate: float | None
    avg_realized_return_pct: float | None


class SignalStatSchema(BaseModel):
    key: str
    n: int
    hits: int
    hit_rate: float | None


class SnapshotRowSchema(BaseModel):
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


class ForecastReportSchema(BaseModel):
    kpi: AccuracyKpiSchema
    by_horizon: list[HorizonStatSchema]
    by_direction: list[DirectionStatSchema]
    by_regime: list[RegimeStatSchema]
    by_signal: list[SignalStatSchema]
    recent: list[SnapshotRowSchema]


class GradeOutcomeRowSchema(BaseModel):
    grade: str
    n: int
    avg_rel_floating_qoq: float | None
    median_rel_floating_qoq: float | None
    positive_share: float | None
    avg_sales_qoq: float | None
    sales_n: int


class ComponentRowSchema(BaseModel):
    key: str
    n: int
    spearman: float | None
    top_minus_bottom_quintile: float | None


class MarketBacktestReportSchema(BaseModel):
    ran_at: datetime
    params: dict
    n_observations: int
    n_areas: int
    base_quarters: list[int]
    grade_outcomes: list[GradeOutcomeRowSchema]
    component_predictiveness: list[ComponentRowSchema]


class MarketBacktestResponseSchema(BaseModel):
    report: MarketBacktestReportSchema | None


class EventBucketRowSchema(BaseModel):
    key: str
    n: int
    avg_return_pct: float
    excess_pct: float   # 기준선 대비 — 절대값이 아니라 이 값으로 읽는다
    positive_rate: float
    reliable: bool


class NewsEventStudyReportSchema(BaseModel):
    ran_at: datetime
    params: dict
    horizon_days: int
    total: int
    baseline_pct: float
    top_week_share: float
    warnings: list[str]
    by_event: list[EventBucketRowSchema]
    by_sentiment: list[EventBucketRowSchema]


class NewsEventStudyResponseSchema(BaseModel):
    report: NewsEventStudyReportSchema | None
