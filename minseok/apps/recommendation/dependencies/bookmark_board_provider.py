from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from hub.dependencies.commercial_data_provider import get_commercial_data_port
from hub.dependencies.stock_status_provider import get_stock_status_port
from recommendation.adapter.outbound.pg.bookmark_pg_repository import BookmarkPgRepository
from recommendation.app.ports.input.bookmark_board_use_case import BookmarkBoardUseCase
from recommendation.app.use_cases.bookmark_board_interactor import BookmarkBoardInteractor


def get_bookmark_board_use_case(
    stock_statuses: StockStatusPort = Depends(get_stock_status_port),
    market: CommercialDataPort = Depends(get_commercial_data_port),
    db: AsyncSession = Depends(get_db),
) -> BookmarkBoardUseCase:
    return BookmarkBoardInteractor(
        bookmarks=BookmarkPgRepository(session=db),
        stock_statuses=stock_statuses,
        market=market,
    )
