"""가격 도달 알림 스캔 계약 DTO([6]) — 허브 스캔(소비)과 recommendation(구현)을 잇는다."""
from __future__ import annotations

from dataclasses import dataclass, field

from hub.app.dtos.bookmark_alert_dto import AlertEmail, TelegramMessage


@dataclass(frozen=True)
class ActivePriceAlert:
    """활성 가격 조건 1건 — 수신 거부 회원 제외는 구현(recommendation) 몫."""

    alert_id: int
    user_id: int
    ticker: str
    target_price: float
    direction: str  # above | below


@dataclass(frozen=True)
class PriceAlertScanReport:
    """스캔 1회 결과 — 발송은 n8n 몫이라 emails/telegrams를 조립까지만 담는다."""

    alerts_scanned: int
    symbols_scanned: int
    triggered: int
    emails: list[AlertEmail] = field(default_factory=list)
    telegrams: list[TelegramMessage] = field(default_factory=list)
