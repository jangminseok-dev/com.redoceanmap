from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.adapter.outbound.exaone_semantic_adapter import ExaoneSemanticAdapter
from hub.adapter.outbound.langchain_chat_engine_adapter import LangchainChatEngineAdapter
from hub.adapter.outbound.pg.langchain_session_pg_repository import (
    LangchainSessionPgRepository,
)
from hub.app.ports.input.langchain_semantic_use_case import LangchainSemanticUseCase
from hub.app.ports.output.market_news_search_port import MarketNewsSearchPort
from hub.app.use_cases.langchain_semantic_interactor import LangchainSemanticInteractor
from hub.dependencies.market_news_search_provider import get_market_news_search_port


def get_langchain_semantic_use_case(
    db: AsyncSession = Depends(get_db),
    market_news: MarketNewsSearchPort = Depends(get_market_news_search_port),
) -> LangchainSemanticUseCase:
    return LangchainSemanticInteractor(
        # 분류기는 ROM 1.0과 같은 어댑터를 그대로 쓴다 — 두 버전이 같은 의도 판정을 공유한다
        llm=ExaoneSemanticAdapter(),
        engine=LangchainChatEngineAdapter(),
        market_news=market_news,
        sessions=LangchainSessionPgRepository(db),
    )
