from __future__ import annotations

from abc import ABC, abstractmethod

from game.domain.market.price_intervention import PriceIntervention


class GameInterventionRepository(ABC):
    """관리자 주가 개입 영속.

    계정 리포지토리와 합치지 않는다 — 지갑·포지션·원장은 한 트랜잭션으로 묶여야 하는
    한 덩어리지만, 개입은 그 트랜잭션과 아무 관계가 없고 소비자도 다르다(가격 조회 경로).
    """

    @abstractmethod
    async def list_in_window(
        self, epoch_id: int, tick: int, window_ticks: int
    ) -> tuple[PriceIntervention, ...]:
        """`tick` 시점 가격 계산에 필요한 개입들.

        창 밖(오래돼 기여가 0)과 미래(`from_tick > tick`)는 빼고 준다 — 가격 조회마다
        도는 경로라 여기서 걸러야 전체가 일정 비용으로 유지된다.
        """
        ...

    @abstractmethod
    async def create(
        self,
        epoch_id: int,
        scope: str,
        target: str,
        target_name: str,
        from_tick: int,
        shock_pct: float,
        drift_pct_per_day: float,
        duration_days: int,
        headline: str,
        note: str | None,
        created_by: int,
    ) -> PriceIntervention:
        """개입 한 건 저장. `from_tick`은 호출 시점의 현재 틱이어야 한다."""
        ...

    @abstractmethod
    async def list_recent(self, epoch_id: int, limit: int) -> tuple[PriceIntervention, ...]:
        """운영 화면용 이력(최신순). 창 밖 개입도 함께 준다."""
        ...
