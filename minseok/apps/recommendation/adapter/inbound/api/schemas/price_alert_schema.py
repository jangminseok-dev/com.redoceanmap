from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PriceAlertCreateRequest(BaseModel):
    ticker: str
    target_price: float
    direction: str  # above(이상 도달) | below(이하 도달)


class PriceAlertResponse(BaseModel):
    id: int
    ticker: str
    target_price: float
    direction: str
    active: bool
    triggered_at: datetime | None = None
    created_at: datetime


class PriceAlertListResponse(BaseModel):
    alerts: list[PriceAlertResponse]
    max_active: int


class PriceAlertMyselfResponse(BaseModel):
    name: str
    description: str
    endpoints: list[str]
