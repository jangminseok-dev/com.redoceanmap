from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.bookmark_directory_dto import BookmarkedStock
from hub.app.ports.output.bookmark_directory_port import BookmarkDirectoryPort
from recommendation.adapter.outbound.orm.bookmark_orm import BookmarkOrm


class BookmarkDirectoryGateway(BookmarkDirectoryPort):
    """허브의 BookmarkDirectoryPort를 recommendation(스포크)이 구현한다.

    전 사용자 횡단 조회 전용 — RecommendationDirectoryGateway와 같은 직접 조회 선례.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def stock_bookmarks(self) -> list[BookmarkedStock]:
        rows = (await self._session.execute(
            select(BookmarkOrm.user_id, BookmarkOrm.target_key, BookmarkOrm.label)
            .where(BookmarkOrm.target_type == "stock")
            .order_by(BookmarkOrm.user_id, BookmarkOrm.target_key)
        )).all()
        return [
            BookmarkedStock(user_id=user_id, ticker=target_key, label=label)
            for user_id, target_key, label in rows
        ]
