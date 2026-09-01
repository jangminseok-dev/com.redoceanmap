from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PriceAlertDraft:
    """가격 조건 등록 입력 — 검증(방향 어휘·양수 가격·상한)은 인터랙터 몫."""

    user_id: int
    ticker: str
    target_price: float
    direction: str  # above | below


@dataclass(frozen=True)
class StoredPriceAlert:
    """저장된 가격 조건 1행."""

    id: int
    ticker: str
    target_price: float
    direction: str
    active: bool
    triggered_at: datetime | None
    created_at: datetime
