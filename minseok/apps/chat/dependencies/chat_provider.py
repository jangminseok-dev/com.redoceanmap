from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from chat.adapter.outbound.pg.conversation_pg_repository import ConversationPgRepository
from chat.app.ports.input.chat_use_case import ChatUseCase
from chat.app.use_cases.chat_interactor import ChatInteractor
from core.database import get_db
from hub.app.ports.output.area_finance_port import AreaFinancePort
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.gemini_answer_port import GeminiAnswerPort
from hub.app.ports.output.market_news_search_port import MarketNewsSearchPort
from hub.app.ports.output.news_search_port import NewsSearchPort
from hub.app.ports.output.recommendation_record_port import RecommendationRecordPort
from hub.app.ports.output.forecast_refit_port import ForecastRefitPort
from hub.app.ports.output.fundamental_read_port import FundamentalReadPort
from hub.app.ports.output.stock_analysis_port import StockAnalysisPort
from hub.app.ports.output.stock_forecast_port import StockForecastPort
from hub.app.ports.output.paper_decision_port import PaperDecisionPort
from hub.app.ports.output.stock_signal_board_port import StockSignalBoardPort
from hub.app.ports.output.user_profile_port import UserProfilePort
from hub.dependencies.area_finance_provider import get_area_finance_port
from hub.dependencies.commercial_data_provider import get_commercial_data_port
from hub.dependencies.forecast_refit_provider import get_forecast_refit_port
from hub.dependencies.fundamental_read_provider import get_fundamental_read_port
from hub.dependencies.gemini_provider import get_gemini_answer_port
from hub.dependencies.market_news_search_provider import get_market_news_search_port
from hub.dependencies.news_search_provider import get_news_search_port
from hub.dependencies.recommendation_record_provider import get_recommendation_record_port
from hub.dependencies.stock_analysis_provider import get_stock_analysis_port
from hub.dependencies.stock_forecast_provider import get_stock_forecast_port
from hub.dependencies.paper_trading_provider import get_paper_decision_port
from hub.dependencies.stock_signal_board_provider import get_stock_signal_board_port
from hub.dependencies.user_profile_provider import get_user_profile_port


def get_chat_use_case(
    market: CommercialDataPort = Depends(get_commercial_data_port),
    recorder: RecommendationRecordPort = Depends(get_recommendation_record_port),
    stocks: StockAnalysisPort = Depends(get_stock_analysis_port),
    news: NewsSearchPort = Depends(get_news_search_port),
    market_news: MarketNewsSearchPort = Depends(get_market_news_search_port),
    gemini: GeminiAnswerPort = Depends(get_gemini_answer_port),
    forecaster: StockForecastPort = Depends(get_stock_forecast_port),
    fundamentals: FundamentalReadPort = Depends(get_fundamental_read_port),
    profiles: UserProfilePort = Depends(get_user_profile_port),
    refit: ForecastRefitPort = Depends(get_forecast_refit_port),
    signals: StockSignalBoardPort = Depends(get_stock_signal_board_port),
    paper: PaperDecisionPort = Depends(get_paper_decision_port),
    finance: AreaFinancePort = Depends(get_area_finance_port),
    db: AsyncSession = Depends(get_db),
) -> ChatUseCase:
    return ChatInteractor(
        market=market,
        recorder=recorder,
        conversations=ConversationPgRepository(session=db),
        stocks=stocks,
        news=news,
        market_news=market_news,
        gemini=gemini,
        forecaster=forecaster,
        fundamentals=fundamentals,
        profiles=profiles,
        refit=refit,
        signals=signals,
        paper=paper,
        finance=finance,
    )
