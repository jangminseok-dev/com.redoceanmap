from __future__ import annotations

from market.app.dtos.area_ranking_dto import AreaRankingQuery, AreaRankingRow, AreaRankingView
from market.app.ports.input.area_ranking_use_case import AreaRankingUseCase
from market.app.ports.output.area_ranking_repository import AreaRankingRepositoryPort


class AreaRankingInteractor(AreaRankingUseCase):
    """상권 디렉터리 대장 — 차원 + 매출·점포 집계를 상권별로 합치고 파생 지표를 낸다.

    정렬은 하지 않는다. 지표를 다 실어 보내고 정렬·검색은 소비자(프론트)가 한다 —
    1,650행이면 클라이언트 필터가 왕복보다 빠르고, `admin/areas`가 이미 그 선례다.
    """

    def __init__(self, repo: AreaRankingRepositoryPort) -> None:
        self._repo = repo

    async def list_ranking(self, query: AreaRankingQuery) -> AreaRankingView:
        latest = await self._repo.latest_quarter()
        areas = await self._repo.find_areas(query.district_name, query.division_code)
        if latest is None or not areas:
            return AreaRankingView(year_quarter=latest, rows=[])

        prev = _prev_quarter(latest)
        sales = await self._repo.find_sales([latest, prev], query.service_code)
        stores = await self._repo.find_stores(latest, query.service_code)

        latest_sales = {s.trdar_code: s.monthly_sales for s in sales if s.year_quarter == latest}
        prev_sales = {s.trdar_code: s.monthly_sales for s in sales if s.year_quarter == prev}
        store_map = {s.trdar_code: s for s in stores}

        rows = []
        for a in areas:
            sale = latest_sales.get(a.trdar_code)
            st = store_map.get(a.trdar_code)
            rows.append(AreaRankingRow(
                trdar_code=a.trdar_code,
                trdar_name=a.trdar_name,
                district_name=a.district_name,
                dong_name=a.dong_name,
                division_code=a.division_code,
                division_name=a.division_name,
                lat=a.lat,
                lng=a.lng,
                monthly_sales=sale,
                store_count=st.store_count if st else None,
                sales_per_store=_per_store(sale, st.store_count if st else None),
                sales_qoq=_qoq(sale, prev_sales.get(a.trdar_code)),
                closure_rate=st.closure_rate if st else None,
            ))
        return AreaRankingView(year_quarter=latest, rows=rows)


def _prev_quarter(year_quarter: int) -> int:
    """20251 → 20244 (연도 경계 처리)."""
    year, q = divmod(year_quarter, 10)
    return (year - 1) * 10 + 4 if q == 1 else year_quarter - 1


def _per_store(sales: int | None, stores: int | None) -> int | None:
    if not sales or not stores:  # 점포 0은 나눗셈 불가이자 의미도 없다
        return None
    return round(sales / stores)


def _qoq(now: int | None, before: int | None) -> float | None:
    if now is None or not before:  # 직전 분기 결측·0이면 변화율을 만들 수 없다
        return None
    return round((now - before) / before * 100, 1)
