from __future__ import annotations

from market.app.dtos.area_detail_dto import AreaDetailQuery, AreaDetailView
from market.app.ports.input.area_detail_use_case import AreaDetailUseCase
from market.app.ports.output.area_detail_repository import AreaDetailRepositoryPort
from market.domain.services.area_narrator import narrate


class AreaDetailInteractor(AreaDetailUseCase):
    """상권 상세 대장 — 팩트별 최신 분기 스냅샷을 조립하고 해석 문장을 붙인다."""

    def __init__(self, detail: AreaDetailRepositoryPort) -> None:
        self._detail = detail

    async def get_detail(self, query: AreaDetailQuery) -> AreaDetailView | None:
        header = await self._detail.find_header(query.trdar_code)
        if header is None:
            return None

        service = await self._detail.resolve_service(query.trdar_code, query.service_code)
        sales_mix = (
            await self._detail.find_sales_mix(query.trdar_code, service.code)
            if service else None
        )
        resident = await self._detail.find_resident(query.trdar_code)
        working = await self._detail.find_working(query.trdar_code)
        apartment = await self._detail.find_apartment(query.trdar_code)
        spending = await self._detail.find_spending(query.trdar_code)
        floating = await self._detail.find_floating_rhythm(query.trdar_code)
        facility = await self._detail.find_facility(query.trdar_code)
        service_ranking = await self._detail.find_service_ranking(query.trdar_code)
        permit_churn = await self._detail.find_permit_churn(query.trdar_code)

        return AreaDetailView(
            trdar_code=header.trdar_code,
            trdar_name=header.trdar_name,
            district_name=header.district_name,
            service_code=service.code if service else None,
            service_name=service.name if service else None,
            sales_mix=sales_mix,
            resident=resident,
            working=working,
            apartment=apartment,
            spending=spending,
            floating=floating,
            facility=facility,
            permit_churn=permit_churn,
            service_ranking=service_ranking,
            insights=narrate(
                sales_mix, resident, working, spending, floating, facility, apartment,
                permit_churn,
            ),
        )
