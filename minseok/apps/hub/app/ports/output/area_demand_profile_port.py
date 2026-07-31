from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.area_demand_profile_dto import AreaDemandProfile


class AreaDemandProfilePort(ABC):
    """상권 수요 분포 조회 추상. game(소비)과 market(구현)을 잇는다.

    `CommercialDataPort`를 확장하지 않고 새로 만든 이유:

    1. 그쪽은 이미 메서드 7개로 chat·admin **두 소비자**를 물고 있다. 게임 전용 메서드를
       얹으면 게이트웨이와 그 스텁 테스트 전부가 게임 사정으로 흔들린다.
    2. 소비자별 계약 분리 선례가 이미 있다 — RecommendationDirectory/Record,
       StockAnalysis/StockForecast, StockDatasetStats.
    3. 필요한 것이 원시 통계 요약이 아니라 **분포 프로필**이라 계약의 결이 다르다.
    """

    @abstractmethod
    async def get_demand_profile(
        self, trdar_code: int, service_code: str, year_quarter: int
    ) -> AreaDemandProfile | None:
        """상권 1곳 × 업종 1개의 수요 분포. 해당 분기 자료가 없으면 None."""
        ...
