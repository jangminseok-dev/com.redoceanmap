"""알림 발송 상태 계약 DTO — dedupe(같은 신호 반복 발송 방지)의 상태 단위."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveredSignal:
    """마지막으로 통지한 (사용자, 종목, 방향) 1건."""

    user_id: int
    ticker: str
    direction: str  # UP | DOWN
