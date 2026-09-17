from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.area_backtest_report_dto import (
    AreaBacktestReportInfo,
    ComponentRow,
    GradeOutcomeRow,
)
from hub.app.ports.output.area_backtest_report_port import AreaBacktestReportPort
from market.adapter.outbound.orm.area_backtest_report_orm import AreaBacktestReportOrm


class AreaBacktestReportGateway(AreaBacktestReportPort):
    """허브 AreaBacktestReportPort 구현 — 최신 실행 1행의 payload를 계약 DTO로 매핑.

    payload 키는 area_score_backtester가 정의 — 누락 키는 .get() 관용(구버전 리포트 공존).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest(self) -> AreaBacktestReportInfo | None:
        row = (await self._session.execute(
            select(AreaBacktestReportOrm).order_by(AreaBacktestReportOrm.id.desc()).limit(1)
        )).scalar()
        if row is None:
            return None
        payload = row.payload or {}
        return AreaBacktestReportInfo(
            ran_at=row.ran_at,
            params=row.params or {},
            n_observations=payload.get("n_observations", 0),
            n_areas=payload.get("n_areas", 0),
            base_quarters=payload.get("base_quarters", []),
            grade_outcomes=[
                GradeOutcomeRow(
                    grade=g.get("grade", ""),
                    n=g.get("n", 0),
                    avg_rel_floating_qoq=g.get("avg_rel_floating_qoq"),
                    median_rel_floating_qoq=g.get("median_rel_floating_qoq"),
                    positive_share=g.get("positive_share"),
                    avg_sales_qoq=g.get("avg_sales_qoq"),
                    sales_n=g.get("sales_n", 0),
                    avg_closure_next4=g.get("avg_closure_next4"),
                    closure_n=g.get("closure_n", 0),
                )
                for g in payload.get("grade_outcomes", [])
            ],
            component_predictiveness=[
                ComponentRow(
                    key=c.get("key", ""),
                    n=c.get("n", 0),
                    spearman=c.get("spearman"),
                    top_minus_bottom_quintile=c.get("top_minus_bottom_quintile"),
                )
                for c in payload.get("component_predictiveness", [])
            ],
        )
