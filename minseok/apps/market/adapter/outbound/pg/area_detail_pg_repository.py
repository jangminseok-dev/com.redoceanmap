from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.apartment_orm import ApartmentOrm
from market.adapter.outbound.orm.consumption_orm import ConsumptionOrm
from market.adapter.outbound.orm.estimated_sales_orm import EstimatedSalesOrm
from market.adapter.outbound.orm.floating_population_orm import FloatingPopulationOrm
from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.resident_population_orm import ResidentPopulationOrm
from market.adapter.outbound.orm.service_category_orm import ServiceCategoryOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.adapter.outbound.orm.working_population_orm import WorkingPopulationOrm
from market.app.dtos.area_stats_dto import AreaHeader, ServiceRef
from market.app.ports.output.area_detail_repository import AreaDetailRepositoryPort
from market.domain.value_objects.area_profile_vo import (
    AgeBand,
    ApartmentProfile,
    FloatingRhythm,
    ResidentProfile,
    SalesMix,
    SpendingCategory,
    SpendingProfile,
    WorkingProfile,
)

_SPENDING_LABELS = [
    ("food", "식료품"),
    ("clothing", "의류·신발"),
    ("household", "생활용품"),
    ("medical", "의료비"),
    ("transport", "교통"),
    ("leisure", "여가"),
    ("culture", "문화"),
    ("education", "교육"),
    ("entertainment", "유흥"),
]

_AGE_BANDS = ["10", "20", "30", "40", "50", "60+"]
_AGE_COLS = ["age_10", "age_20", "age_30", "age_40", "age_50", "age_60_plus"]


class AreaDetailPgRepository(AreaDetailRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_header(self, trdar_code: int) -> AreaHeader | None:
        dong = aliased(RegionOrm)  # 행정동(level2)
        gu = aliased(RegionOrm)    # 자치구(level1)
        row = (await self._session.execute(
            select(TradeAreaOrm.code, TradeAreaOrm.name, gu.name)
            .outerjoin(dong, TradeAreaOrm.region_code == dong.code)
            .outerjoin(gu, dong.parent_code == gu.code)
            .where(TradeAreaOrm.code == trdar_code)
        )).first()
        if row is None:
            return None
        code, name, gu_name = row
        return AreaHeader(trdar_code=code, trdar_name=name, district_name=gu_name or "")

    async def resolve_service(self, trdar_code: int, service_code: str | None) -> ServiceRef | None:
        # area_stats와 동일 규칙 — 미지정이면 최신 분기 매출 최대 업종
        if service_code is None:
            latest_quarter = (await self._session.execute(
                select(func.max(EstimatedSalesOrm.year_quarter))
                .where(EstimatedSalesOrm.trdar_code == trdar_code)
            )).scalar()
            if latest_quarter is None:
                return None
            service_code = (await self._session.execute(
                select(EstimatedSalesOrm.service_code)
                .where(
                    EstimatedSalesOrm.trdar_code == trdar_code,
                    EstimatedSalesOrm.year_quarter == latest_quarter,
                )
                .order_by(EstimatedSalesOrm.monthly_sales_amount.desc())
                .limit(1)
            )).scalar()
        name = (await self._session.execute(
            select(ServiceCategoryOrm.name).where(ServiceCategoryOrm.code == service_code)
        )).scalar()
        if name is None:
            return None
        return ServiceRef(code=service_code, name=name)

    async def find_sales_mix(self, trdar_code: int, service_code: str) -> SalesMix | None:
        r = (await self._session.execute(
            select(EstimatedSalesOrm)
            .where(
                EstimatedSalesOrm.trdar_code == trdar_code,
                EstimatedSalesOrm.service_code == service_code,
            )
            .order_by(EstimatedSalesOrm.year_quarter.desc())
            .limit(1)
        )).scalar()
        if r is None:
            return None
        return SalesMix(
            year_quarter=r.year_quarter,
            weekday_amount=r.weekday_sales_amount,
            weekend_amount=r.weekend_sales_amount,
            by_day={
                "mon": r.mon_sales_amount, "tue": r.tue_sales_amount,
                "wed": r.wed_sales_amount, "thu": r.thu_sales_amount,
                "fri": r.fri_sales_amount, "sat": r.sat_sales_amount,
                "sun": r.sun_sales_amount,
            },
            by_time={
                "t00_06": r.time_00_06_sales_amount, "t06_11": r.time_06_11_sales_amount,
                "t11_14": r.time_11_14_sales_amount, "t14_17": r.time_14_17_sales_amount,
                "t17_21": r.time_17_21_sales_amount, "t21_24": r.time_21_24_sales_amount,
            },
            by_gender={"male": r.male_sales_amount, "female": r.female_sales_amount},
            by_age={
                "age10": r.age_10_sales_amount, "age20": r.age_20_sales_amount,
                "age30": r.age_30_sales_amount, "age40": r.age_40_sales_amount,
                "age50": r.age_50_sales_amount, "age60Plus": r.age_60_plus_sales_amount,
            },
            monthly_count=r.monthly_sales_count,
            monthly_amount=r.monthly_sales_amount,
            weekday_count=r.weekday_sales_count,
            weekend_count=r.weekend_sales_count,
            count_by_age={
                "age10": r.age_10_sales_count, "age20": r.age_20_sales_count,
                "age30": r.age_30_sales_count, "age40": r.age_40_sales_count,
                "age50": r.age_50_sales_count, "age60Plus": r.age_60_plus_sales_count,
            },
        )

    async def find_resident(self, trdar_code: int) -> ResidentProfile | None:
        r = (await self._session.execute(
            select(ResidentPopulationOrm)
            .where(ResidentPopulationOrm.trdar_code == trdar_code)
            .order_by(ResidentPopulationOrm.year_quarter.desc())
            .limit(1)
        )).scalar()
        if r is None:
            return None
        return ResidentProfile(
            year_quarter=r.year_quarter,
            total=r.total_resident_pop,
            by_age=_age_bands(r, "resident_pop"),
            total_households=r.total_household_count,
            apartment_households=r.apartment_household_count,
        )

    async def find_working(self, trdar_code: int) -> WorkingProfile | None:
        r = (await self._session.execute(
            select(WorkingPopulationOrm)
            .where(WorkingPopulationOrm.trdar_code == trdar_code)
            .order_by(WorkingPopulationOrm.year_quarter.desc())
            .limit(1)
        )).scalar()
        if r is None:
            return None
        return WorkingProfile(
            year_quarter=r.year_quarter,
            total=r.total_working_pop,
            by_age=_age_bands(r, "working_pop"),
        )

    async def find_apartment(self, trdar_code: int) -> ApartmentProfile | None:
        r = (await self._session.execute(
            select(ApartmentOrm)
            .where(ApartmentOrm.trdar_code == trdar_code)
            .order_by(ApartmentOrm.year_quarter.desc())
            .limit(1)
        )).scalar()
        if r is None:
            return None
        return ApartmentProfile(
            year_quarter=r.year_quarter,
            complex_count=r.complex_count,
            avg_price=r.avg_price,
            avg_area=r.avg_area,
        )

    async def find_floating_rhythm(self, trdar_code: int) -> FloatingRhythm | None:
        r = (await self._session.execute(
            select(FloatingPopulationOrm)
            .where(FloatingPopulationOrm.trdar_code == trdar_code)
            .order_by(FloatingPopulationOrm.year_quarter.desc())
            .limit(1)
        )).scalar()
        if r is None:
            return None
        return FloatingRhythm(
            year_quarter=r.year_quarter,
            weekday_pop=(r.mon_floating_pop + r.tue_floating_pop + r.wed_floating_pop
                         + r.thu_floating_pop + r.fri_floating_pop),
            weekend_pop=r.sat_floating_pop + r.sun_floating_pop,
        )

    async def find_spending(self, trdar_code: int) -> SpendingProfile | None:
        r = (await self._session.execute(
            select(ConsumptionOrm)
            .where(ConsumptionOrm.trdar_code == trdar_code)
            .order_by(ConsumptionOrm.year_quarter.desc())
            .limit(1)
        )).scalar()
        if r is None:
            return None
        categories = [
            SpendingCategory(key=key, label=label, amount=amount)
            for key, label in _SPENDING_LABELS
            if (amount := getattr(r, f"{key}_expenditure")) is not None
        ]
        categories.sort(key=lambda c: c.amount, reverse=True)
        return SpendingProfile(
            year_quarter=r.year_quarter,
            monthly_avg_income=r.monthly_avg_income,
            total_expenditure=r.total_expenditure,
            by_category=categories,
        )


def _age_bands(row: object, suffix: str) -> list[AgeBand]:
    return [
        AgeBand(
            band=band,
            male=getattr(row, f"male_{col}_{suffix}"),
            female=getattr(row, f"female_{col}_{suffix}"),
        )
        for band, col in zip(_AGE_BANDS, _AGE_COLS)
    ]
