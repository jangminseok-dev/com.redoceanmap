from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_ranking_dto import (
    AreaRankingQuery,
    AreaRankingView,
    AreaShowcaseView,
)


class AreaRankingUseCase(ABC):
    """상권 디렉터리 — 전 상권을 지표와 함께 훑는다(정렬·검색은 소비자 몫)."""

    @abstractmethod
    async def list_ranking(self, query: AreaRankingQuery) -> AreaRankingView:
        """조건에 맞는 상권이 없으면 rows가 빈 리스트(404 아님 — 목록 화면은 떠야 한다)."""
        ...

    @abstractmethod
    async def showcase(self) -> AreaShowcaseView:
        """비로그인 첫 화면용 — 자치구당 1곳씩 점포당 매출 상위 소수만, 최소 필드로.

        `list_ranking`과 달리 **여기서는 정렬·절단을 한다**. 소비자가 고정된
        카드 N장이라 "무엇이 상위인가"를 화면마다 다시 정의할 여지가 없고,
        공개 응답이므로 페이로드를 소비자에게 맡길 수 없다.
        입력이 없다 — 개수·컷오프는 인터랙터의 상수다(공개 엔드포인트에서
        `?limit=N`을 열면 캐시 키가 무한 증식한다).
        """
        ...
