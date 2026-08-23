from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.alert_delivery_dto import DeliveredSignal


class AlertDeliveryPort(ABC):
    """알림 발송 상태 계약 — 허브 bookmark_alert(소비)와 recommendation(구현·영속)을 잇는다.

    "같은 신호가 지속되는 동안 매일 반복 발송"(v1 한계)을 막는 dedupe의 상태 저장소.
    스캔 1회가 전 사용자 전량이라 상태는 매 실행 **전체 교체**된다 — 신호가 꺼진
    (사용자, 종목)은 다음 교체에서 자연히 사라져, 재발생 시 새 알림이 나간다.
    """

    @abstractmethod
    async def last_signals(self) -> list[DeliveredSignal]:
        """마지막 스캔이 남긴 통지 상태 전부 — 없으면 빈 리스트."""
        ...

    @abstractmethod
    async def replace(self, signals: list[DeliveredSignal]) -> None:
        """통지 상태를 통째로 교체한다(전량 스캔 전제 — 부분 갱신 아님)."""
        ...
