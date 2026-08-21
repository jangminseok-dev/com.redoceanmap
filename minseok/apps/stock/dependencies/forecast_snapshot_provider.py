from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.forecast_snapshot_port import ForecastSnapshotPort
from stock.adapter.outbound.gateways.forecast_snapshot_gateway import ForecastSnapshotGateway
from stock.adapter.outbound.pg.forecast_history_pg_repository import ForecastHistoryPgRepository
from stock.adapter.outbound.pg.forecast_snapshot_pg_repository import ForecastSnapshotPgRepository
from stock.adapter.outbound.pg.signal_config_pg_repository import SignalConfigPgRepository
from stock.adapter.outbound.yfinance_earnings_calendar_adapter import (
    YFinanceEarningsCalendarAdapter,
)
from stock.app.use_cases.forecast_snapshot_interactor import ForecastSnapshotInteractor
from stock.app.use_cases.stock_forecast_interactor import StockForecastInteractor


def get_forecast_snapshot_gateway(db: AsyncSession = Depends(get_db)) -> ForecastSnapshotPort:
    """허브 ForecastSnapshotPort 구현 프로바이더 — main.py가 dependency_overrides로 주입.

    forecaster는 market_data=None으로 조립 — 스냅샷은 저장 봉 기준 기록이라
    미수집 종목의 라이브 폴백(즉석 벤더 호출)을 원천 차단한다. 어닝 어댑터는 별개로
    주입한다(시세 폴백 차단과 무관 — 발표일 조회는 일 1회 캐시 경량 호출).
    configs는 forecaster와 같은 인스턴스 — breakdown·direction이 같은 조합으로 계산된다.
    """
    history = ForecastHistoryPgRepository(session=db)
    configs = SignalConfigPgRepository(session=db)
    return ForecastSnapshotGateway(
        use_case=ForecastSnapshotInteractor(
            forecaster=StockForecastInteractor(
                history=history, market_data=None,
                earnings=YFinanceEarningsCalendarAdapter(),
                configs=configs,
            ),
            history=history,
            snapshots=ForecastSnapshotPgRepository(session=db),
            configs=configs,
        )
    )
