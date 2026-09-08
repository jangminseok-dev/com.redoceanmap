from __future__ import annotations

from sqlalchemy import Float, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from market.adapter.outbound.orm.commercial_change_orm import CommercialChangeOrm
from market.adapter.outbound.orm.estimated_sales_orm import EstimatedSalesOrm
from market.adapter.outbound.orm.floating_population_orm import FloatingPopulationOrm
from market.adapter.outbound.orm.service_category_orm import ServiceCategoryOrm
from market.adapter.outbound.orm.store_orm import StoreOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.app.dtos.area_demand_profile_dto import AreaDemandProfile
from market.app.ports.output.area_demand_profile_port import AreaDemandProfilePort
_WEEKDAY_COLUMNS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_HOUR_COLUMNS = ("time_00_06", "time_06_11", "time_11_14", "time_14_17", "time_17_21", "time_21_24")
_AGE_COLUMNS = ("age_10", "age_20", "age_30", "age_40", "age_50", "age_60_plus")
_GENDER_COLUMNS = ("male", "female")

_EMPTY_6 = (0.0,) * 6
_EMPTY_7 = (0.0,) * 7
_EMPTY_2 = (0.0,) * 2


def _shares(values: list[float]) -> tuple[float, ...]:
    """합이 1.0이 되도록 정규화. 총합이 0이면 전부 0.0(자료 없음과 균등분포를 구분한다)."""
    total = sum(values)
    if total <= 0:
        return tuple(0.0 for _ in values)
    return tuple(round(v / total, 6) for v in values)


class AreaDemandProfilePgRepository(AreaDemandProfilePort):
    """수요 프로필 조회 — 조회 6번으로 끝난다.

    상권·업종 매출, 유동인구, 점포, 변화지표, 업종 서울 기준선, 백분위 3종(한 쿼리).
    상권 1곳 조회라 인덱스가 받쳐주고, 백분위는 1,650행 스캔이다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_quarter(self) -> int | None:
        value = await self._session.scalar(select(func.max(EstimatedSalesOrm.year_quarter)))
        return int(value) if value is not None else None

    async def get_demand_profile(
        self, trdar_code: int, service_code: str, year_quarter: int
    ) -> AreaDemandProfile | None:
        names = await self._session.execute(
            select(TradeAreaOrm.name, ServiceCategoryOrm.name)
            .select_from(TradeAreaOrm)
            .join(ServiceCategoryOrm, ServiceCategoryOrm.code == service_code)
            .where(TradeAreaOrm.code == trdar_code)
        )
        row = names.first()
        if row is None:
            return None  # 없는 상권이거나 없는 업종
        trdar_name, service_name = row

        sales = await self._session.scalar(
            select(EstimatedSalesOrm).where(
                EstimatedSalesOrm.trdar_code == trdar_code,
                EstimatedSalesOrm.service_code == service_code,
                EstimatedSalesOrm.year_quarter == year_quarter,
            )
        )
        floating = await self._session.scalar(
            select(FloatingPopulationOrm).where(
                FloatingPopulationOrm.trdar_code == trdar_code,
                FloatingPopulationOrm.year_quarter == year_quarter,
            )
        )
        store = await self._session.scalar(
            select(StoreOrm).where(
                StoreOrm.trdar_code == trdar_code,
                StoreOrm.service_code == service_code,
                StoreOrm.year_quarter == year_quarter,
            )
        )
        change = await self._session.scalar(
            select(CommercialChangeOrm).where(
                CommercialChangeOrm.trdar_code == trdar_code,
                CommercialChangeOrm.year_quarter == year_quarter,
            )
        )

        industry = await self._industry_baseline(service_code, year_quarter)
        percentiles = await self._percentiles(trdar_code, service_code, year_quarter, store)

        return AreaDemandProfile(
            trdar_code=trdar_code,
            trdar_name=trdar_name,
            service_code=service_code,
            service_name=service_name,
            year_quarter=year_quarter,
            observed_monthly_sales_amount=int(sales.monthly_sales_amount) if sales else 0,
            observed_monthly_sales_count=int(sales.monthly_sales_count) if sales else 0,
            observed_store_count=int(store.store_count) if store else 0,
            observed_similar_store_count=int(store.similar_industry_store_count or 0)
            if store
            else 0,
            observed_closure_rate=float(store.closure_rate) if store else 0.0,
            observed_operating_months_avg=float(change.operating_months_avg) if change else 0.0,
            area_weekday_share=self._share_of(sales, _WEEKDAY_COLUMNS, "sales_amount", _EMPTY_7),
            area_hour_share=self._share_of(sales, _HOUR_COLUMNS, "sales_amount", _EMPTY_6),
            area_gender_share=self._share_of(sales, _GENDER_COLUMNS, "sales_amount", _EMPTY_2),
            area_age_share=self._share_of(sales, _AGE_COLUMNS, "sales_amount", _EMPTY_6),
            floating_total=int(floating.total_floating_pop) if floating else 0,
            floating_hour_share=self._share_of(floating, _HOUR_COLUMNS, "floating_pop", _EMPTY_6),
            floating_gender_share=self._share_of(
                floating, _GENDER_COLUMNS, "floating_pop", _EMPTY_2
            ),
            floating_age_share=self._share_of(floating, _AGE_COLUMNS, "floating_pop", _EMPTY_6),
            industry_hour_share=industry["hour"],
            industry_gender_share=industry["gender"],
            industry_age_share=industry["age"],
            saturation_percentile=percentiles["saturation"],
            closure_rate_percentile=percentiles["closure"],
            operating_months_percentile=percentiles["operating"],
            has_sales=sales is not None,
            has_store=store is not None,
            has_floating=floating is not None,
        )

    @staticmethod
    def _share_of(orm, prefixes: tuple[str, ...], suffix: str, empty: tuple[float, ...]):
        if orm is None:
            return empty
        return _shares([float(getattr(orm, f"{p}_{suffix}") or 0) for p in prefixes])

    async def _industry_baseline(self, service_code: str, year_quarter: int) -> dict:
        """이 업종이 서울 전체에서 원래 누구에게·언제 팔리는가.

        상권의 분포와 이 기준선을 비교하는 것이 적합도의 핵심이다 — "이 업종 매출의 62%는
        20대에서 나오는데 이 상권 유동인구의 절반은 50대"를 말할 수 있게 된다.
        """
        columns = [
            func.coalesce(func.sum(getattr(EstimatedSalesOrm, f"{p}_sales_amount")), 0)
            for p in (*_HOUR_COLUMNS, *_GENDER_COLUMNS, *_AGE_COLUMNS)
        ]
        result = await self._session.execute(
            select(*columns).where(
                EstimatedSalesOrm.service_code == service_code,
                EstimatedSalesOrm.year_quarter == year_quarter,
            )
        )
        row = result.first()
        values = [float(v or 0) for v in row] if row else [0.0] * 14
        return {
            "hour": _shares(values[0:6]),
            "gender": _shares(values[6:8]),
            "age": _shares(values[8:14]),
        }

    async def _percentiles(
        self, trdar_code: int, service_code: str, year_quarter: int, store
    ) -> dict:
        """서울 안에서의 상대 위치. 임계값을 상식으로 정하지 않기 위한 재료다.

        market이 이미 겪은 함정 — 시설 임계값을 "5곳 이상"으로 잡았더니 중앙값 0·p90 1인
        분포에서 전 서울 2상권만 발화했다. 절대값이 아니라 분위수로 잡는다.
        """
        empty = {"saturation": 0.0, "closure": 0.0, "operating": 0.0}
        if store is None:
            return empty

        # 포화도 = 유사업종 점포수 ÷ 유동인구 (경쟁 밀도). 유동인구가 0인 상권은 제외한다.
        density = (
            select(
                (
                    func.cast(StoreOrm.similar_industry_store_count, Float)
                    / func.nullif(FloatingPopulationOrm.total_floating_pop, 0)
                ).label("value")
            )
            .select_from(StoreOrm)
            .join(
                FloatingPopulationOrm,
                (FloatingPopulationOrm.trdar_code == StoreOrm.trdar_code)
                & (FloatingPopulationOrm.year_quarter == StoreOrm.year_quarter),
            )
            .where(
                StoreOrm.service_code == service_code,
                StoreOrm.year_quarter == year_quarter,
            )
            .subquery()
        )

        my_density = await self._session.scalar(
            select(
                func.cast(StoreOrm.similar_industry_store_count, Float)
                / func.nullif(FloatingPopulationOrm.total_floating_pop, 0)
            )
            .select_from(StoreOrm)
            .join(
                FloatingPopulationOrm,
                (FloatingPopulationOrm.trdar_code == StoreOrm.trdar_code)
                & (FloatingPopulationOrm.year_quarter == StoreOrm.year_quarter),
            )
            .where(
                StoreOrm.trdar_code == trdar_code,
                StoreOrm.service_code == service_code,
                StoreOrm.year_quarter == year_quarter,
            )
        )
        saturation = await self._rank(density, my_density)

        closure_sub = select(StoreOrm.closure_rate.label("value")).where(
            StoreOrm.service_code == service_code,
            StoreOrm.year_quarter == year_quarter,
        ).subquery()
        closure = await self._rank(closure_sub, float(store.closure_rate))

        operating_sub = select(CommercialChangeOrm.operating_months_avg.label("value")).where(
            CommercialChangeOrm.year_quarter == year_quarter
        ).subquery()
        my_operating = await self._session.scalar(
            select(CommercialChangeOrm.operating_months_avg).where(
                CommercialChangeOrm.trdar_code == trdar_code,
                CommercialChangeOrm.year_quarter == year_quarter,
            )
        )
        operating = await self._rank(operating_sub, my_operating)

        return {"saturation": saturation, "closure": closure, "operating": operating}

    async def _rank(self, subquery, value: float | None) -> float:
        """`value`가 분포에서 차지하는 백분위(0.0~1.0). 값이 없으면 0.0."""
        if value is None:
            return 0.0
        result = await self._session.scalar(
            select(
                func.coalesce(
                    func.sum(case((subquery.c.value <= value, 1.0), else_=0.0))
                    / func.nullif(func.count(subquery.c.value), 0),
                    0.0,
                )
            )
        )
        return round(float(result or 0.0), 4)
