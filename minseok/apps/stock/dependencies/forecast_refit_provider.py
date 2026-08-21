from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.forecast_refit_port import ForecastRefitPort
from stock.adapter.outbound.gateways.forecast_refit_gateway import ForecastRefitGateway
from stock.adapter.outbound.pg.forecast_snapshot_pg_repository import ForecastSnapshotPgRepository
from stock.adapter.outbound.pg.refit_report_pg_repository import RefitReportPgRepository
from stock.adapter.outbound.pg.signal_config_pg_repository import SignalConfigPgRepository
from stock.app.use_cases.forecast_refit_interactor import ForecastRefitInteractor


def get_forecast_refit_gateway(db: AsyncSession = Depends(get_db)) -> ForecastRefitPort:
    """허브 ForecastRefitPort 구현 프로바이더 — main.py가 dependency_overrides로 주입."""
    return ForecastRefitGateway(
        use_case=ForecastRefitInteractor(
            snapshots=ForecastSnapshotPgRepository(session=db),
            configs=SignalConfigPgRepository(session=db),
            reports=RefitReportPgRepository(session=db),
        )
    )
