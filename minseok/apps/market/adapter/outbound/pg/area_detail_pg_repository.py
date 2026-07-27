from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.apartment_orm import ApartmentOrm
from market.adapter.outbound.orm.consumption_orm import ConsumptionOrm
from market.adapter.outbound.orm.estimated_sales_orm import EstimatedSalesOrm
from market.adapter.outbound.orm.facility_orm import FacilityOrm
from market.adapter.outbound.orm.floating_population_orm import FloatingPopulationOrm
from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.resident_population_orm import ResidentPopulationOrm
from market.adapter.outbound.orm.service_category_orm import ServiceCategoryOrm
from market.adapter.outbound.orm.store_orm import StoreOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.adapter.outbound.orm.working_population_orm import WorkingPopulationOrm
from market.app.dtos.area_stats_dto import AreaHeader, ServiceRef
from market.app.ports.output.area_detail_repository import AreaDetailRepositoryPort
from market.domain.value_objects.area_profile_vo import (
    AgeBand,
    ApartmentProfile,
    FacilityProfile,
    FloatingRhythm,
    ResidentProfile,
    SalesMix,
    ServiceRank,
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
            # 빈칸은 "그 구간 세대 없음" — 전 행이 최소 한 구간을 갖고 있어 결측이 아니다
            price_bands={
                "under1b": r.price_under_1b_count or 0,
                "b1": r.price_1b_count or 0,
                "b2": r.price_2b_count or 0,
                "b3": r.price_3b_count or 0,
                "b4": r.price_4b_count or 0,
                "b5": r.price_5b_count or 0,
                "over6b": r.price_over_6b_count or 0,
            },
            area_bands={
                "under66": r.area_under_66_count or 0,
                "a66": r.area_66_count or 0,
                "a99": r.area_99_count or 0,
                "a132": r.area_132_count or 0,
                "a165": r.area_165_count or 0,
            },
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

    async def find_service_ranking(self, trdar_code: int, limit: int = 12) -> list[ServiceRank]:
        latest = (await self._session.execute(
            select(func.max(EstimatedSalesOrm.year_quarter))
            .where(EstimatedSalesOrm.trdar_code == trdar_code)
        )).scalar()
        if latest is None:
            return []
        prev = latest - 1 if latest % 10 != 1 else (latest // 10 - 1) * 10 + 4

        sales_rows = (await self._session.execute(
            select(
                EstimatedSalesOrm.service_code,
                EstimatedSalesOrm.year_quarter,
                func.sum(EstimatedSalesOrm.monthly_sales_amount),
            )
            .where(
                EstimatedSalesOrm.trdar_code == trdar_code,
                EstimatedSalesOrm.year_quarter.in_([latest, prev]),
            )
            .group_by(EstimatedSalesOrm.service_code, EstimatedSalesOrm.year_quarter)
        )).all()
        store_rows = (await self._session.execute(
            select(
                StoreOrm.service_code,
                func.sum(StoreOrm.store_count),
                func.avg(StoreOrm.closure_rate),
            )
            .where(StoreOrm.trdar_code == trdar_code, StoreOrm.year_quarter == latest)
            .group_by(StoreOrm.service_code)
        )).all()
        names = dict((await self._session.execute(
            select(ServiceCategoryOrm.code, ServiceCategoryOrm.name)
        )).all())

        now = {c: int(v or 0) for c, yq, v in sales_rows if yq == latest}
        before = {c: int(v or 0) for c, yq, v in sales_rows if yq == prev}
        stores = {c: (int(n or 0), float(r) if r is not None else None) for c, n, r in store_rows}

        out = []
        for code, sales in sorted(now.items(), key=lambda kv: -kv[1])[:limit]:
            count, closure = stores.get(code, (None, None))
            base = before.get(code)
            out.append(ServiceRank(
                code=code,
                name=names.get(code, code),
                monthly_sales=sales,
                store_count=count,
                sales_per_store=round(sales / count) if count else None,
                sales_qoq=round((sales - base) / base * 100, 1) if base else None,
                closure_rate=round(closure, 1) if closure is not None else None,
            ))
        return out

    async def find_facility(self, trdar_code: int) -> FacilityProfile | None:
        r = (await self._session.execute(
            select(FacilityOrm)
            .where(FacilityOrm.trdar_code == trdar_code)
            .order_by(FacilityOrm.year_quarter.desc())
            .limit(1)
        )).scalar()
        if r is None:
            return None
        return FacilityProfile(
            year_quarter=r.year_quarter,
            total=r.total_facility_count,
            subway_stations=r.subway_station_count,
            bus_stops=r.bus_stop_count,
            universities=r.university_count,
            department_stores=r.department_store_count,
            hospitals=r.general_hospital_count + r.hospital_count,
            gateway=r.railway_station_count + r.bus_terminal_count + r.airport_count,
            schools=(r.kindergarten_count + r.elementary_school_count
                     + r.middle_school_count + r.high_school_count),
            nightlife=r.theater_count + r.lodging_count,
            convenience=(r.bank_count + r.pharmacy_count
                         + r.supermarket_count + r.public_office_count),
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
