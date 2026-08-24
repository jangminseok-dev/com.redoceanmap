from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.commercial_data_dto import (
    AreaInsight,
    AreaOverviewRow,
    AreaRawStat,
    AreaScoreInfo,
    AreaSummary,
    PermitChurnInfo,
    ServiceCode,
)
from hub.app.dtos.dataset_stat_dto import DatasetStat


class CommercialDataPort(ABC):
    """허브가 스포크에 위임하는 상권 데이터 조회 추상.

    허브는 이 포트(추상)만 알고 어떤 스포크가 구현하는지 모른다(스타 토폴로지 허브 격리).
    구현은 스포크(market)가 제공하고, 합성 루트(main.py)에서 주입한다.
    """

    @abstractmethod
    async def get_service_codes(self) -> list[ServiceCode]:
        """선택 가능한 업종 코드 목록을 반환한다."""
        ...

    @abstractmethod
    async def get_area_summary(self) -> AreaSummary:
        """전체 상권 기본정보(좌표 포함) + 최신 분기 + 상권별 월매출 합계·전년 동분기 대비(%)를 반환한다."""
        ...

    @abstractmethod
    async def get_area_raw_stats(
        self, trdar_codes: list[int], service_code: str, quarter: int
    ) -> dict[int, AreaRawStat]:
        """지정 상권들의 원시 통계(매출·점포·유동인구·상권변화)를 반환한다."""
        ...

    @abstractmethod
    async def get_area_scores(self, trdar_codes: list[int]) -> dict[int, AreaScoreInfo]:
        """지정 상권들의 시도 벤치마크 대비 종합점수 — 산출 근거 팩트가 없는 상권은 제외."""
        ...

    @abstractmethod
    async def get_area_insights(
        self, trdar_codes: list[int], service_code: str | None = None
    ) -> dict[int, tuple[AreaInsight, ...]]:
        """지정 상권들의 해석 문장 — 고객 프로필·배후 수요·소비·객단가.

        지도 오버레이만 보던 인사이트를 채팅에도 공급한다. 근거 팩트가 없는 상권은 제외.
        """
        ...

    @abstractmethod
    async def get_area_permit_churn(
        self, trdar_codes: list[int], months: int = 12
    ) -> dict[int, PermitChurnInfo]:
        """지정 상권들의 인허가 기준 업소 교체 — 최근 months개월 개업·폐업 수.

        분기 팩트가 답하는 "얼마나 있나"에 "지금 늘고 있나"를 더한다. 인허가가 붙은
        업소가 없는 상권은 제외(열화 동작 — 소비자가 라인을 생략한다).
        """
        ...

    @abstractmethod
    async def get_area_overview(self) -> list[AreaOverviewRow]:
        """어드민 상권 목록 — 전 상권의 최신 분기 점포수·폐업률·월매출 집계."""
        ...

    @abstractmethod
    async def get_dataset_stats(self) -> list[DatasetStat]:
        """어드민 데이터소스 현황 — market 데이터셋별 행수·최신 시점."""
        ...
