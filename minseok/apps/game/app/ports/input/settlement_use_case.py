from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.settlement_dto import SettlementListView, SettlementQuery


class SettlementUseCase(ABC):
    """분기 결산 유스케이스 — 밀린 분기를 확정하고 목록을 낸다."""

    @abstractmethod
    async def run_and_list(self, query: SettlementQuery) -> SettlementListView:
        """**지연 실행**: 조회 시점에 밀린 분기를 순서대로 확정한다.

        cron이 없으므로 조회가 곧 정산 시점이다. 멱등하므로 여러 번 불러도 안전하다.
        """
        ...
