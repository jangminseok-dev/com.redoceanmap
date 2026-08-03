from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class PriceBarSchema(BaseModel):
    ts: datetime  # 봉 시작 시각(UTC)
    open: float
    high: float
    low: float
    close: float
    volume: int


class ChartPatternSchema(BaseModel):
    name: str  # head_and_shoulders 등 기계용 식별자
    label: str
    startIndex: int  # bars 배열 위치
    endIndex: int
    confidence: float  # 이상적 형태와의 기하학적 근접도(0~1) — 적중 확률이 아니다
    points: list[tuple[int, float]]  # (bars 인덱스, 종가)
    note: str  # 통상적 해석 — 매매 지시나 예측이 아니다


class PriceHistoryResponse(BaseModel):
    symbol: str
    resolvedTicker: str  # DB에 실제 저장된 티커(예: 005930.KS)
    timeframe: str
    bars: list[PriceBarSchema]  # ts 오름차순
    live: bool = False  # true = 미수집 종목 — yfinance 라이브 이력 폴백
    patterns: list[ChartPatternSchema] = []  # 종가 곡선에서 관측된 형태(신뢰도 상위)


class StockNewsItemSchema(BaseModel):
    id: int
    title: str
    source: str
    url: str
    publishedAt: datetime | None
    sentiment: float | None  # -1.0 ~ +1.0, 라벨 없으면 null
    eventType: str | None
    confidence: float | None


class FundamentalSnapshotSchema(BaseModel):
    asOf: date
    source: str  # yfinance | dart
    per: float | None
    pbr: float | None
    roe: float | None
    debtToEquity: float | None
    fcf: float | None
    marketCap: float | None
    eps: float | None
    bps: float | None


class FundamentalInsightSchema(BaseModel):
    key: str
    tone: str  # positive | neutral | warning
    text: str


class FundamentalsResponse(BaseModel):
    symbol: str
    snapshots: list[FundamentalSnapshotSchema]  # 소스별 최신 각 1건
    insights: list[FundamentalInsightSchema]    # 규칙 기반 해석(dart 우선 병합)
