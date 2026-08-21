from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from recommendation.adapter.outbound.pg.bookmark_pg_repository import BookmarkPgRepository
from recommendation.app.ports.input.bookmark_use_case import BookmarkUseCase
from recommendation.app.use_cases.bookmark_interactor import BookmarkInteractor


def get_bookmark_use_case(db: AsyncSession = Depends(get_db)) -> BookmarkUseCase:
    return BookmarkInteractor(bookmarks=BookmarkPgRepository(session=db))
