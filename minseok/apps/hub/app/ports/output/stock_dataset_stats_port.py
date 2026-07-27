from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.dataset_stat_dto import DatasetStat


class StockDatasetStatsPort(ABC):
    """stock 소유 데이터셋의 적재 현황 조회 협력 — admin(소비)과 stock(구현)을 잇는다.

    저장은 각 StoragePort가 맡는 조회 전용 계약이다(Record ↔ Directory 분리 선례).
    `CommercialDataPort.get_dataset_stats`와 시그니처·DTO가 같아 소비자는 두 목록을 잇기만 한다.
    """

    @abstractmethod
    async def get_dataset_stats(self) -> list[DatasetStat]:
        """뉴스·라벨·펀더멘털·예측 스냅샷·주가 봉의 행수와 최신 적재 시각."""
        ...
