from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AreaMeta:
    """상권 차원 정보 — 랭킹 행의 뼈대."""

    trdar_code: int
    trdar_name: str
    district_name: str
    dong_name: str
    division_code: str
    division_name: str
    lat: float
    lng: float


@dataclass(frozen=True)
class SalesAgg:
    """상권별 매출 합 — 최신/직전 분기 각각."""

    trdar_code: int
    year_quarter: int
    monthly_sales: int


@dataclass(frozen=True)
class StoreAgg:
    """상권별 점포 합·폐업률 평균 — 최신 분기."""

    trdar_code: int
    store_count: int
    closure_rate: float


class AreaRankingRepositoryPort(ABC):
    """랭킹 집계 조회 아웃바운드 포트 — 파생 계산(점포당 매출·QoQ)은 인터랙터가 맡는다."""

    @abstractmethod
    async def latest_quarter(self) -> int | None:
        """매출 팩트의 최신 분기. 데이터가 없으면 None."""
        ...

    @abstractmethod
    async def find_areas(
        self, district_name: str | None, division_code: str | None
    ) -> list[AreaMeta]:
        """조건에 맞는 상권 차원 목록."""
        ...

    @abstractmethod
    async def find_sales(
        self, quarters: list[int], service_code: str | None
    ) -> list[SalesAgg]:
        """지정 분기들의 상권별 매출 합(업종 지정 시 해당 업종만)."""
        ...

    @abstractmethod
    async def find_stores(
        self, year_quarter: int, service_code: str | None
    ) -> list[StoreAgg]:
        """최신 분기의 상권별 점포 합·폐업률 평균."""
        ...
