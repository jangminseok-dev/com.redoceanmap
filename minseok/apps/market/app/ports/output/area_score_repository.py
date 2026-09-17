from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_score_dto import AreaScoreHeader
from market.domain.value_objects.area_score_vo import AreaScoreInputs, QuarterValue


class AreaScoreRepositoryPort(ABC):
    """상권 스코어링 입력 팩트 조회 아웃바운드 포트 — 계산은 도메인 스코어러가 맡는다."""

    @abstractmethod
    async def find_header(self, trdar_code: int) -> AreaScoreHeader | None:
        """상권명 + 자치구명 + 시도 코드. 상권이 없으면 None."""
        ...

    @abstractmethod
    async def find_sales_series(self, trdar_code: int, quarters: int) -> list[QuarterValue]:
        """최근 quarters개 분기의 전 업종 합계 매출 — year_quarter 오름차순."""
        ...

    @abstractmethod
    async def find_floating_series(self, trdar_code: int, quarters: int) -> list[QuarterValue]:
        """최근 quarters개 분기의 총 유동인구 — year_quarter 오름차순."""
        ...

    @abstractmethod
    async def find_score_inputs(self, trdar_code: int) -> AreaScoreInputs | None:
        """점수 v2 입력 — 최신 점포 분기 기준 상권 값. 점포 팩트가 없으면 None."""
        ...

    @abstractmethod
    async def find_city_score_medians(self, sido_code: str) -> AreaScoreInputs | None:
        """같은 기준으로 계산한 시도 안 상권들의 중앙값 — 벤치마크(분기 적재 때만 재계산)."""
        ...
