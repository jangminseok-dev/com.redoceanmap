from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SnapshotCaptureRequest(BaseModel):
    tickers: list[str]
    horizons: list[int] = Field(default_factory=lambda: [5])


class SnapshotCaptureResponse(BaseModel):
    captured: int
    skipped: list[str]
    as_of: datetime | None = None  # 캡처가 본 최신 봉 기준일 — 배치가 모의투자 step의 as_of로 되돌려 보낸다


class SnapshotScoreResponse(BaseModel):
    scored: int
    pending: int
