from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation.adapter.outbound.orm.bookmark_orm import BookmarkOrm
from recommendation.app.ports.output.bookmark_repository import BookmarkRepositoryPort
from recommendation.domain.entities.bookmark_entity import Bookmark


class BookmarkPgRepository(BookmarkRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, bookmark: Bookmark) -> Bookmark:
        # 중복이면 아무것도 바꾸지 않고 기존 행을 돌려준다 — 재등록으로 label이
        # 조용히 덮이는 것보다 "처음 찜했을 때 이름"이 남는 쪽이 예측 가능하다.
        await self._session.execute(
            pg_insert(BookmarkOrm)
            .values(
                user_id=bookmark.user_id, target_type=bookmark.target_type,
                target_key=bookmark.target_key, label=bookmark.label,
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "target_type", "target_key"]
            )
        )
        await self._session.commit()
        row = (await self._session.execute(
            select(BookmarkOrm).where(
                BookmarkOrm.user_id == bookmark.user_id,
                BookmarkOrm.target_type == bookmark.target_type,
                BookmarkOrm.target_key == bookmark.target_key,
            )
        )).scalar_one()
        return self._to_entity(row)

    async def find_by_user(self, user_id: int) -> list[Bookmark]:
        rows = (await self._session.execute(
            select(BookmarkOrm)
            .where(BookmarkOrm.user_id == user_id)
            .order_by(BookmarkOrm.created_at.desc(), BookmarkOrm.id.desc())
        )).scalars().all()
        return [self._to_entity(r) for r in rows]

    async def count_by_user(self, user_id: int) -> int:
        return int((await self._session.execute(
            select(func.count(BookmarkOrm.id)).where(BookmarkOrm.user_id == user_id)
        )).scalar())

    async def delete(self, user_id: int, target_type: str, target_key: str) -> bool:
        result = await self._session.execute(
            delete(BookmarkOrm).where(
                BookmarkOrm.user_id == user_id,
                BookmarkOrm.target_type == target_type,
                BookmarkOrm.target_key == target_key,
            )
        )
        await self._session.commit()
        return result.rowcount > 0

    @staticmethod
    def _to_entity(r: BookmarkOrm) -> Bookmark:
        return Bookmark(
            id=r.id, user_id=r.user_id, target_type=r.target_type,
            target_key=r.target_key, label=r.label, created_at=r.created_at,
        )
