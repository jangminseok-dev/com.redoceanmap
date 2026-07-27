from __future__ import annotations

import logging

from market.app.dtos.cartographer_dto import CartographerQuery, CartographerResponse
from market.app.ports.input.cartographer_use_case import CartographerUseCase
from market.app.ports.output.cartographer_record_port import CartographerRecordPort

logger = logging.getLogger(__name__)


class CartographerInteractor(CartographerUseCase):
    """상권 데이터 조회 (market) 대장 — 자기소개 스켈레톤. 담당: 상권 데이터의 지도 제작자 — 전국 확장의 기반."""

    def __init__(self, record: CartographerRecordPort) -> None:
        self._record = record

    async def introduce_myself(self, query: CartographerQuery) -> CartographerResponse:
        await self._record.record(subject="introduce_myself", note=f"{query.name} 자기소개 관찰")
        return CartographerResponse(
            id=query.id,
            name=query.name,
            introduction="서울 상권 실데이터(3NF: 차원 5 + 팩트 8)를 조회합니다. GET /market/areas 상권 목록(자치구 필터), GET /market/areas/ranking 상권 디렉터리(전 상권 매출·점포당매출·전분기 대비, 자치구·상권구분·업종 필터), GET /market/trdar/{code}/area 개별 상권 정보, GET /market/trdar/{code}/detail 최신 분기 구조 분해(요일·시간대·성별·연령대 매출, 상주·직장인구, 소비, 아파트)와 규칙 기반 해석 문장을 제공합니다. 매출·점포는 2021~2025년 20개 분기를 보유합니다.",
        )
