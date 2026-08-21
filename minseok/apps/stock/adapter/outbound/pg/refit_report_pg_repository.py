from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.forecast_refit_report_orm import ForecastRefitReportOrm
from stock.app.dtos.forecast_refit_dto import RefitReportView
from stock.app.ports.output.refit_report_repository import RefitReportRepositoryPort


class RefitReportPgRepository(RefitReportRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, params: dict, payload: dict) -> None:
        self._session.add(ForecastRefitReportOrm(params=params, payload=payload))
        await self._session.commit()

    async def latest(self) -> RefitReportView | None:
        row = (await self._session.execute(
            select(ForecastRefitReportOrm)
            .order_by(ForecastRefitReportOrm.id.desc())
            .limit(1)
        )).scalar()
        if row is None:
            return None
        return RefitReportView(ran_at=row.ran_at, params=row.params or {}, payload=row.payload or {})
