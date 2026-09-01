from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.price_alert_scan_dto import ActivePriceAlert


class PriceAlertDirectoryPort(ABC):
    """가격 조건 횡단 열람·트리거 기록 계약 — 허브 스캔(소비)과 recommendation(구현)을 잇는다.

    BookmarkDirectoryPort와 같은 발송 대상 열람 의미론: **알림 수신을 끈 회원
    (user_alert_settings)은 active_alerts()에서 제외**된다. dedupe는
    `user_alert_deliveries`가 아니라 one-shot 비활성화다 — 그 테이블은 북마크 스캔이
    전체 교체하므로 다른 스캔이 공유하면 서로의 상태를 지운다(마이그레이션 주석 참조).
    """

    @abstractmethod
    async def active_alerts(self) -> list[ActivePriceAlert]:
        ...

    @abstractmethod
    async def mark_triggered(self, alert_ids: list[int]) -> None:
        """통지한 조건을 비활성화한다(active=false + triggered_at). 재알림은 재등록."""
        ...

    @abstractmethod
    async def telegram_chat_ids(self, user_ids: list[int]) -> dict[int, str]:
        """user_id → 텔레그램 chat_id. 미등록 회원은 키 자체가 없다(I-7과 동일)."""
        ...
