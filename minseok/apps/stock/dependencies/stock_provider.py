from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.stock_analysis_port import StockAnalysisPort
from stock.adapter.outbound.exaone_sentiment_adapter import ExaoneSentimentAdapter
from stock.adapter.outbound.gateways.stock_analysis_gateway import StockAnalysisGateway
from stock.adapter.outbound.pg.demand_pg_repository import DemandPgRepository
from stock.adapter.outbound.pg.news_pg_repository import NewsPgRepository
from stock.adapter.outbound.pg.signal_config_pg_repository import SignalConfigPgRepository
from stock.adapter.outbound.yfinance_market_data_adapter import YFinanceMarketDataAdapter
from stock.app.ports.input.stock_use_case import StockUseCase
from stock.app.use_cases.stock_interactor import StockInteractor
from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.services.outlook_predictor import OutlookPredictor


def get_stock_use_case(db: AsyncSession = Depends(get_db)) -> StockUseCase:
    return StockInteractor(
        market_data=YFinanceMarketDataAdapter(),
        sentiment=ExaoneSentimentAdapter(),
        predictor=OutlookPredictor(),
        config=AnalysisConfig.forecast_signal(),             # 활성 조합 조회 실패 시 폴백(검증 조합 상수)
        news=NewsPgRepository(session=db),
        demand=DemandPgRepository(session=db),
        configs=SignalConfigPgRepository(session=db),        # 예측·스냅샷과 같은 활성 검증 조합
    )


def get_stock_analysis_gateway(
    use_case: StockUseCase = Depends(get_stock_use_case),
) -> StockAnalysisPort:
    """허브 StockAnalysisPort 구현 프로바이더 — main.py가 dependency_overrides로 주입."""
    return StockAnalysisGateway(use_case=use_case)


def get_stock_use_case_batch(db: AsyncSession = Depends(get_db)) -> StockUseCase:
    """자동화(시그널 스캔) 전용 — 수요 기록(demand) 없이 분석만. 크론이 수요 통계를 오염시키지 않게."""
    return StockInteractor(
        market_data=YFinanceMarketDataAdapter(),
        sentiment=ExaoneSentimentAdapter(),
        predictor=OutlookPredictor(),
        config=AnalysisConfig.forecast_signal(),
        news=NewsPgRepository(session=db),
        configs=SignalConfigPgRepository(session=db),
    )


def get_stock_analysis_gateway_batch(
    use_case: StockUseCase = Depends(get_stock_use_case_batch),
) -> StockAnalysisPort:
    """허브 배치 분석 포트 구현 프로바이더 — main.py가 dependency_overrides로 주입."""
    return StockAnalysisGateway(use_case=use_case)
