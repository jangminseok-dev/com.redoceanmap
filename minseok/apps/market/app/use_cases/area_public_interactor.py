from __future__ import annotations

from market.app.dtos.area_detail_dto import AreaDetailQuery
from market.app.dtos.area_public_dto import AreaIndexRow, AreaPublicView
from market.app.dtos.area_score_dto import AreaScoreQuery
from market.app.ports.input.area_detail_use_case import AreaDetailUseCase
from market.app.ports.input.area_public_use_case import AreaPublicUseCase
from market.app.ports.input.area_score_use_case import AreaScoreUseCase
from market.app.ports.output.area_index_repository import AreaIndexRepositoryPort


class AreaPublicInteractor(AreaPublicUseCase):
    """공개 상권 페이지 대장 — 상세·점수 유스케이스를 **조합만** 하고 공개 필드를 고른다.

    새 집계·새 쿼리는 인덱스(차원 목록) 하나뿐이다. 무엇을 내보내지 않는가가 이 슬라이스의
    본체이므로 뷰 DTO(AreaPublicView)의 필드 집합을 테스트가 고정한다.
    """

    def __init__(
        self,
        index: AreaIndexRepositoryPort,
        detail: AreaDetailUseCase,
        score: AreaScoreUseCase,
    ) -> None:
        self._index = index
        self._detail = detail
        self._score = score

    async def get_public(self, trdar_code: int) -> AreaPublicView | None:
        meta = await self._index.find_one(trdar_code)
        if meta is None:
            return None
        detail = await self._detail.get_detail(AreaDetailQuery(trdar_code=trdar_code))
        score_view = await self._score.get_score(AreaScoreQuery(trdar_code=trdar_code))

        # 기준 업종(상세가 자동 선택한 최신 분기 매출 최대 업종)의 랭킹 행 — 랭킹 1위와 다를 수 있다
        rank = None
        if detail is not None and detail.service_code is not None:
            rank = next((r for r in detail.service_ranking if r.code == detail.service_code), None)
        floating = detail.floating if detail is not None else None

        return AreaPublicView(
            trdar_code=meta.trdar_code,
            trdar_name=meta.trdar_name,
            district_name=meta.district_name,
            division_name=meta.division_name,
            year_quarter=_year_quarter(detail),
            score=score_view.score if score_view is not None else None,
            service_code=detail.service_code if detail is not None else None,
            service_name=detail.service_name if detail is not None else None,
            store_count=rank.store_count if rank else None,
            sales_per_store=rank.sales_per_store if rank else None,
            sales_qoq=rank.sales_qoq if rank else None,
            closure_rate=rank.closure_rate if rank else None,
            floating_pop=(floating.weekday_pop + floating.weekend_pop) if floating else None,
            insights=list(detail.insights) if detail is not None else [],
        )

    async def list_index(self) -> list[AreaIndexRow]:
        return await self._index.list_all()


def _year_quarter(detail) -> int | None:
    if detail is None:
        return None
    if detail.sales_mix is not None:
        return detail.sales_mix.year_quarter
    if detail.floating is not None:
        return detail.floating.year_quarter
    return None
