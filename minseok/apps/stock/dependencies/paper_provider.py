from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.paper_decision_port import PaperDecisionPort
from hub.app.ports.output.paper_trading_port import PaperTradingPort
from stock.adapter.outbound.alias_symbol_directory import AliasSymbolDirectory
from stock.adapter.outbound.exaone_decision_adapter import ExaoneDecisionAdapter
from stock.adapter.outbound.gateways.paper_trading_gateway import PaperDecisionGateway, PaperTradingGateway
from stock.adapter.outbound.pg.paper_account_pg_repository import PaperAccountPgRepository
from stock.adapter.outbound.pg.paper_feed_pg_repository import PaperFeedPgRepository
from stock.app.ports.input.paper_use_case import PaperUseCase
from stock.app.use_cases.paper_interactor import PaperInteractor


def get_paper_use_case(db: AsyncSession = Depends(get_db)) -> PaperUseCase:
    return PaperInteractor(
        accounts=PaperAccountPgRepository(session=db),
        feed=PaperFeedPgRepository(session=db),
        policy=ExaoneDecisionAdapter(),
        directory=AliasSymbolDirectory(),
    )


def get_paper_trading_gateway(use_case: PaperUseCase = Depends(get_paper_use_case)) -> PaperTradingPort:
    return PaperTradingGateway(use_case)


def get_paper_decision_gateway(use_case: PaperUseCase = Depends(get_paper_use_case)) -> PaperDecisionPort:
    return PaperDecisionGateway(use_case)
