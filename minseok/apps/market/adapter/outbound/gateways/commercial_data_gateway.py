from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from hub.app.dtos.commercial_data_dto import (
    AreaInfo,
    AreaInsight,
    AreaOverviewRow,
    AreaRankingInfo,
    AreaRawStat,
    AreaScoreComponent,
    AreaScoreInfo,
    AreaSummary,
    AreaTrendPoint,
    PermitChurnInfo,
    ServiceCode,
)
from hub.app.dtos.dataset_stat_dto import DatasetStat
from market.adapter.outbound.pg.area_detail_pg_repository import AreaDetailPgRepository
from market.adapter.outbound.pg.area_ranking_pg_repository import AreaRankingPgRepository
from market.adapter.outbound.pg.area_score_pg_repository import AreaScorePgRepository
from market.app.dtos.area_detail_dto import AreaDetailQuery
from market.app.dtos.area_ranking_dto import AreaRankingQuery
from market.app.dtos.area_score_dto import AreaScoreQuery
from market.app.use_cases.area_detail_interactor import AreaDetailInteractor
from market.app.use_cases.area_ranking_interactor import AreaRankingInteractor
from market.app.use_cases.area_score_interactor import AreaScoreInteractor
from market.adapter.outbound.orm.change_indicator_orm import ChangeIndicatorOrm
from market.adapter.outbound.orm.commercial_change_benchmark_orm import (
    CommercialChangeBenchmarkOrm,
)
from market.adapter.outbound.orm.commercial_change_orm import CommercialChangeOrm
from market.adapter.outbound.orm.estimated_sales_orm import EstimatedSalesOrm
from market.adapter.outbound.orm.floating_population_orm import FloatingPopulationOrm
from market.adapter.outbound.orm.market_news_article_orm import MarketNewsArticleOrm
from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.service_category_orm import ServiceCategoryOrm
from market.adapter.outbound.orm.store_orm import StoreOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.domain.services.area_scorer import prev_year_quarter
from hub.app.ports.output.commercial_data_port import CommercialDataPort


# 상권 요약 캐시 — chat이 상권 질문마다 부르는데 결과(전 상권 조인 + 최신 분기 매출
# GROUP BY)는 분기 적재 때만 바뀐다. 최신 분기를 버전 키로 삼아 자연 갱신한다 —
# area_score의 시도 벤치마크 캐시(위 _CITY_CACHE)와 같은 방식이고 같은 이유로 TTL·Redis 불요.
_SUMMARY_CACHE: dict[str, tuple[int, AreaSummary]] = {}


class CommercialDataGateway(CommercialDataPort):
    """허브의 CommercialDataPort를 market(스포크)이 구현한다.

    스포크 → 허브 추상에만 의존(스타 토폴로지 허용). 정규화(3NF) 스키마를 조회해
    허브 계약 DTO로 반환한다. 상권명·지역명·업종명·변화지표명은 차원 테이블 조인으로 채운다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_service_codes(self) -> list[ServiceCode]:
        result = await self._session.execute(
            select(ServiceCategoryOrm.code, ServiceCategoryOrm.name).limit(300)
        )
        return [ServiceCode(code=r.code, name=r.name) for r in result.all()]

    async def get_area_summary(self) -> AreaSummary:
        # 버전 키(최신 분기, index-only scan)만 먼저 조회 — 같은 분기면 재집계하지 않는다
        latest_quarter = (
            await self._session.execute(select(func.max(EstimatedSalesOrm.year_quarter)))
        ).scalar()
        hit = _SUMMARY_CACHE.get("area_summary")
        if hit is not None and hit[0] == latest_quarter:
            return hit[1]

        dong = aliased(RegionOrm)  # 행정동(level2)
        gu = aliased(RegionOrm)    # 자치구(level1)
        rows = (await self._session.execute(
            select(TradeAreaOrm, dong.name.label("dong_name"), gu.name.label("gu_name"))
            .outerjoin(dong, TradeAreaOrm.region_code == dong.code)
            .outerjoin(gu, dong.parent_code == gu.code)
        )).all()

        sales_by_code: dict[int, int] = {}
        if latest_quarter:
            result = await self._session.execute(
                select(
                    EstimatedSalesOrm.trdar_code,
                    func.sum(EstimatedSalesOrm.monthly_sales_amount).label("total"),
                )
                .where(EstimatedSalesOrm.year_quarter == latest_quarter)
                .group_by(EstimatedSalesOrm.trdar_code)
            )
            sales_by_code = {r.trdar_code: r.total for r in result.all()}

        # 전년 동분기 대비(%) — phase1 후보 표의 YoY 열(I-10). 전년 결측·0이면 None.
        yoy_by_code: dict[int, float | None] = {}
        if latest_quarter:
            base_quarter = prev_year_quarter(latest_quarter)
            result = await self._session.execute(
                select(
                    EstimatedSalesOrm.trdar_code,
                    func.sum(EstimatedSalesOrm.monthly_sales_amount).label("total"),
                )
                .where(EstimatedSalesOrm.year_quarter == base_quarter)
                .group_by(EstimatedSalesOrm.trdar_code)
            )
            base_by_code = {r.trdar_code: r.total for r in result.all()}
            for code, current in sales_by_code.items():
                base = base_by_code.get(code)
                yoy_by_code[code] = (
                    round((current - base) / base * 100, 2) if base and base > 0 else None
                )

        area_infos = [
            AreaInfo(
                trdar_code=t.code,
                trdar_name=t.name,
                district_name=r.gu_name or "",
                adm_dong_name=r.dong_name or "",
                lat=t.lat,
                lng=t.lng,
                x_coord=t.x_coord,
                y_coord=t.y_coord,
            )
            for t, r in ((row[0], row) for row in rows)
        ]
        summary = AreaSummary(
            areas=area_infos, latest_quarter=latest_quarter,
            sales_by_code=sales_by_code, yoy_by_code=yoy_by_code,
        )
        if latest_quarter is not None:  # 데이터 없는 상태를 캐시하면 적재 후에도 빈 채 남는다
            _SUMMARY_CACHE["area_summary"] = (latest_quarter, summary)
        return summary

    async def get_area_scores(self, trdar_codes: list[int]) -> dict[int, AreaScoreInfo]:
        # area_score 슬라이스(도메인 스코어러 + PG 리포지토리)를 그대로 재사용해 허브 DTO로 변환
        interactor = AreaScoreInteractor(repo=AreaScorePgRepository(session=self._session))
        result: dict[int, AreaScoreInfo] = {}
        for code in trdar_codes:
            view = await interactor.get_score(AreaScoreQuery(trdar_code=code))
            if view is None or view.score is None:
                continue
            result[code] = AreaScoreInfo(
                total=view.score.total,
                grade=view.score.grade,
                components=tuple(
                    AreaScoreComponent(
                        key=c.key, name=c.name, score=c.score,
                        value=c.value, benchmark=c.benchmark,
                    )
                    for c in view.score.components
                ),
                # 분기 추이(I-20) — 슬라이스가 이미 계산하던 것을 버리지 않고 나른다
                trend=tuple(
                    AreaTrendPoint(
                        year_quarter=t.year_quarter,
                        monthly_sales=t.monthly_sales,
                        sales_qoq=t.sales_qoq,
                        total_floating_pop=t.total_floating_pop,
                        floating_qoq=t.floating_qoq,
                        sales_yoy=t.sales_yoy,
                        floating_yoy=t.floating_yoy,
                    )
                    for t in view.trend
                ),
            )
        return result

    async def get_area_ranking(
        self, service_code: str | None = None
    ) -> list[AreaRankingInfo]:
        # area_ranking 슬라이스를 그대로 재사용해 허브 DTO로 변환 — get_area_scores와 같은 형태
        interactor = AreaRankingInteractor(repo=AreaRankingPgRepository(session=self._session))
        view = await interactor.list_ranking(AreaRankingQuery(service_code=service_code))
        return [
            AreaRankingInfo(
                trdar_code=r.trdar_code,
                trdar_name=r.trdar_name,
                district_name=r.district_name,
                dong_name=r.dong_name,
                monthly_sales=r.monthly_sales,
                store_count=r.store_count,
                sales_per_store=r.sales_per_store,
                closure_rate=r.closure_rate,
                change_indicator_name=r.change_indicator_name,
            )
            for r in view.rows
        ]

    async def get_area_insights(
        self, trdar_codes: list[int], service_code: str | None = None
    ) -> dict[int, tuple[AreaInsight, ...]]:
        # area_detail 슬라이스(도메인 서술자 + PG 리포지토리)를 그대로 재사용 — get_area_scores와 같은 형태
        interactor = AreaDetailInteractor(detail=AreaDetailPgRepository(session=self._session))
        result: dict[int, tuple[AreaInsight, ...]] = {}
        for code in trdar_codes:
            view = await interactor.get_detail(
                AreaDetailQuery(trdar_code=code, service_code=service_code)
            )
            if view is None or not view.insights:
                continue
            result[code] = tuple(
                AreaInsight(key=i.key, tone=i.tone, text=i.text) for i in view.insights
            )
        return result

    async def get_area_permit_churn(
        self, trdar_codes: list[int], months: int = 12
    ) -> dict[int, PermitChurnInfo]:
        # get_area_insights와 같은 형태 — area_detail 슬라이스의 PG 리포지토리를 그대로 재사용한다.
        # 상호 표본(recent_openings/closings)은 허브 계약에 싣지 않으므로 sample=0으로 받는다.
        repository = AreaDetailPgRepository(session=self._session)
        result: dict[int, PermitChurnInfo] = {}
        for code in trdar_codes:
            churn = await repository.find_permit_churn(code, months=months, sample=0)
            if churn is None:
                continue  # 인허가가 붙은 업소가 없는 상권 — 소비자가 라인을 생략한다
            result[code] = PermitChurnInfo(
                months=churn.months, opened=churn.opened,
                closed=churn.closed, active=churn.active,
            )
        return result

    async def get_area_overview(self) -> list[AreaOverviewRow]:
        dong = aliased(RegionOrm)
        gu = aliased(RegionOrm)
        area_rows = (await self._session.execute(
            select(TradeAreaOrm.code, TradeAreaOrm.name, dong.name.label("dong_name"), gu.name.label("gu_name"))
            .outerjoin(dong, TradeAreaOrm.region_code == dong.code)
            .outerjoin(gu, dong.parent_code == gu.code)
            .order_by(TradeAreaOrm.code)
        )).all()

        store_quarter = (
            await self._session.execute(select(func.max(StoreOrm.year_quarter)))
        ).scalar()
        store_map: dict[int, tuple[int, float]] = {}
        if store_quarter:
            # closure_rate는 업종별 팩트의 단순평균 — 통계적 정밀도보다 목록 표시 용도
            result = await self._session.execute(
                select(
                    StoreOrm.trdar_code,
                    func.sum(StoreOrm.store_count).label("stores"),
                    func.avg(StoreOrm.closure_rate).label("closure"),
                )
                .where(StoreOrm.year_quarter == store_quarter)
                .group_by(StoreOrm.trdar_code)
            )
            store_map = {r.trdar_code: (r.stores, float(r.closure)) for r in result.all()}

        sales_quarter = (
            await self._session.execute(select(func.max(EstimatedSalesOrm.year_quarter)))
        ).scalar()
        sales_map: dict[int, int] = {}
        if sales_quarter:
            result = await self._session.execute(
                select(
                    EstimatedSalesOrm.trdar_code,
                    func.sum(EstimatedSalesOrm.monthly_sales_amount).label("total"),
                )
                .where(EstimatedSalesOrm.year_quarter == sales_quarter)
                .group_by(EstimatedSalesOrm.trdar_code)
            )
            sales_map = {r.trdar_code: r.total for r in result.all()}

        return [
            AreaOverviewRow(
                trdar_code=r.code,
                trdar_name=r.name,
                gu_name=r.gu_name or "",
                dong_name=r.dong_name or "",
                store_count=store_map[r.code][0] if r.code in store_map else None,
                closure_rate=store_map[r.code][1] if r.code in store_map else None,
                monthly_sales=sales_map.get(r.code),
            )
            for r in area_rows
        ]

    async def get_dataset_stats(self) -> list[DatasetStat]:
        area_count = (
            await self._session.execute(select(func.count(TradeAreaOrm.code)))
        ).scalar() or 0
        stats: list[DatasetStat] = [
            DatasetStat(key="trade_area", name="상권", row_count=area_count, latest_label=None)
        ]
        for key, name, orm in (
            ("estimated_sales", "추정 매출", EstimatedSalesOrm),
            ("store", "점포 현황", StoreOrm),
            ("floating_population", "유동인구", FloatingPopulationOrm),
        ):
            row = (await self._session.execute(
                select(func.count(orm.id), func.max(orm.year_quarter))
            )).one()
            stats.append(DatasetStat(
                key=key, name=name, row_count=row[0],
                latest_label=str(row[1]) if row[1] else None,
            ))
        # 신선도 기준은 발행일(published_at)이 아니라 적재 시각(created_at)이다 —
        # 기사가 뜸한 날에도 수집은 돌고, 옛 기사만 들어와도 발행일은 최신이 아니다.
        news = (await self._session.execute(
            select(func.count(MarketNewsArticleOrm.id), func.max(MarketNewsArticleOrm.created_at))
        )).one()
        stats.append(DatasetStat(
            key="market_news", name="상권 뉴스", row_count=news[0],
            latest_label=None, latest_at=news[1],
        ))
        return stats

    async def get_area_raw_stats(
        self, trdar_codes: list[int], service_code: str, quarter: int
    ) -> dict[int, AreaRawStat]:
        sales_rows = (await self._session.execute(
            select(EstimatedSalesOrm).where(
                EstimatedSalesOrm.trdar_code.in_(trdar_codes),
                EstimatedSalesOrm.service_code == service_code,
                EstimatedSalesOrm.year_quarter == quarter,
            )
        )).scalars().all()
        sales_map = {r.trdar_code: r for r in sales_rows}

        store_rows = (await self._session.execute(
            select(StoreOrm).where(
                StoreOrm.trdar_code.in_(trdar_codes),
                StoreOrm.service_code == service_code,
                StoreOrm.year_quarter == quarter,
            )
        )).scalars().all()
        store_map = {r.trdar_code: r for r in store_rows}

        fp_rows = (await self._session.execute(
            select(FloatingPopulationOrm).where(
                FloatingPopulationOrm.trdar_code.in_(trdar_codes),
                FloatingPopulationOrm.year_quarter == quarter,
            )
        )).scalars().all()
        fp_map = {r.trdar_code: r for r in fp_rows}

        cc_rows = (await self._session.execute(
            select(CommercialChangeOrm, ChangeIndicatorOrm.name.label("indicator_name"))
            .outerjoin(
                ChangeIndicatorOrm,
                CommercialChangeOrm.change_indicator == ChangeIndicatorOrm.code,
            )
            .where(
                CommercialChangeOrm.trdar_code.in_(trdar_codes),
                CommercialChangeOrm.year_quarter == quarter,
            )
        )).all()
        cc_map = {row[0].trdar_code: (row[0], row.indicator_name) for row in cc_rows}

        # 상권 → 시도 코드 해소 후 시도 벤치마크(분기별 지역 평균) 매핑
        dong = aliased(RegionOrm)
        gu = aliased(RegionOrm)
        sido_rows = (await self._session.execute(
            select(TradeAreaOrm.code, gu.parent_code)
            .join(dong, TradeAreaOrm.region_code == dong.code)
            .join(gu, dong.parent_code == gu.code)
            .where(TradeAreaOrm.code.in_(trdar_codes))
        )).all()
        sido_map = {r[0]: r[1] for r in sido_rows}

        bench_rows = (await self._session.execute(
            select(CommercialChangeBenchmarkOrm).where(
                CommercialChangeBenchmarkOrm.year_quarter == quarter
            )
        )).scalars().all()
        bench_map = {b.region_code: b for b in bench_rows}

        result: dict[int, AreaRawStat] = {}
        for code in trdar_codes:
            s = sales_map.get(code)
            st = store_map.get(code)
            fp = fp_map.get(code)
            cc_pair = cc_map.get(code)
            cc = cc_pair[0] if cc_pair else None
            bench = bench_map.get(sido_map.get(code))
            result[code] = AreaRawStat(
                has_sales=s is not None,
                monthly_sales_amount=s.monthly_sales_amount if s else None,
                weekday_sales_amount=s.weekday_sales_amount if s else None,
                has_store=st is not None,
                store_count=st.store_count if st else None,
                closure_rate=st.closure_rate if st else None,
                opening_rate=st.opening_rate if st else None,
                franchise_store_count=st.franchise_store_count if st else None,
                similar_industry_store_count=st.similar_industry_store_count if st else None,
                opening_store_count=st.opening_store_count if st else None,
                closure_store_count=st.closure_store_count if st else None,
                has_fp=fp is not None,
                total_floating_pop=fp.total_floating_pop if fp else None,
                age_10_floating_pop=fp.age_10_floating_pop if fp else None,
                age_20_floating_pop=fp.age_20_floating_pop if fp else None,
                age_30_floating_pop=fp.age_30_floating_pop if fp else None,
                age_40_floating_pop=fp.age_40_floating_pop if fp else None,
                age_50_floating_pop=fp.age_50_floating_pop if fp else None,
                age_60_plus_floating_pop=fp.age_60_plus_floating_pop if fp else None,
                time_00_06_floating_pop=fp.time_00_06_floating_pop if fp else None,
                time_06_11_floating_pop=fp.time_06_11_floating_pop if fp else None,
                time_11_14_floating_pop=fp.time_11_14_floating_pop if fp else None,
                time_14_17_floating_pop=fp.time_14_17_floating_pop if fp else None,
                time_17_21_floating_pop=fp.time_17_21_floating_pop if fp else None,
                time_21_24_floating_pop=fp.time_21_24_floating_pop if fp else None,
                has_cc=cc is not None,
                change_indicator_name=cc_pair[1] if cc_pair else None,
                operating_months_avg=cc.operating_months_avg if cc else None,
                region_operating_months_avg=bench.operating_months_avg if bench else None,
                closure_months_avg=cc.closure_months_avg if cc else None,
                region_closure_months_avg=bench.closure_months_avg if bench else None,
            )
        return result
