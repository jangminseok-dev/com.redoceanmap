from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.stock_forecast_port import StockForecastPort
from stock.adapter.outbound.gateways.stock_forecast_gateway import StockForecastGateway
from stock.adapter.outbound.pg.forecast_history_pg_repository import ForecastHistoryPgRepository
from stock.adapter.outbound.pg.signal_config_pg_repository import SignalConfigPgRepository
from stock.adapter.outbound.pg.stock_board_pg_repository import StockBoardPgRepository
from stock.adapter.outbound.yfinance_earnings_calendar_adapter import (
    YFinanceEarningsCalendarAdapter,
)
from stock.adapter.outbound.yfinance_market_data_adapter import YFinanceMarketDataAdapter
from stock.app.ports.input.stock_forecast_use_case import StockForecastUseCase
from stock.app.use_cases.stock_forecast_interactor import StockForecastInteractor


def get_stock_forecast_use_case(db: AsyncSession = Depends(get_db)) -> StockForecastUseCase:
    return StockForecastInteractor(
        history=ForecastHistoryPgRepository(session=db),
        market_data=YFinanceMarketDataAdapter(),  # 미수집 종목 라이브 폴백
        earnings=YFinanceEarningsCalendarAdapter(),  # 실적 ±2일 관망 강등
        configs=SignalConfigPgRepository(session=db),  # 활성 판정 조합(재적합 승격 반영)
        risk_reports=StockBoardPgRepository(session=db),  # 위험 신호 검증 실측(보드와 같은 최신 리포트)
    )


def get_stock_forecast_gateway(
    use_case: StockForecastUseCase = Depends(get_stock_forecast_use_case),
) -> StockForecastPort:
    """허브 StockForecastPort 구현 프로바이더 — main.py가 dependency_overrides로 주입."""
    return StockForecastGateway(use_case=use_case)
