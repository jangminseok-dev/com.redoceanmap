from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from hub.adapter.outbound.mappers.langchain_session_mapper import (
    LangchainSessionMapper,
    LangchainTurnMapper,
)
from hub.adapter.outbound.orm.langchain_session_orm import (
    LangchainSessionOrm,
    LangchainTurnOrm,
)
from hub.app.ports.output.langchain_session_repository import LangchainSessionRepository
from hub.domain.langchain_chat.session_entity import LangchainSession, LangchainTurn


class LangchainSessionPgRepository(LangchainSessionRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(self, user_id: int | None = None) -> LangchainSession:
        orm = LangchainSessionOrm(user_id=user_id)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return LangchainSessionMapper.to_entity(orm)

    async def get_session(self, session_id: int) -> LangchainSession | None:
        orm = (
            await self._session.execute(
                select(LangchainSessionOrm).where(LangchainSessionOrm.id == session_id)
            )
        ).scalar_one_or_none()
        return LangchainSessionMapper.to_entity(orm) if orm else None

    async def append_turn(
        self, session_id: int, role: str, content: str, destination: str | None = None
    ) -> LangchainTurn:
        result = await self._session.execute(
            insert(LangchainTurnOrm)
            .values(
                session_id=session_id,
                role=role,
                content=content,
                destination=destination,
            )
            .returning(LangchainTurnOrm)
        )
        await self._session.commit()
        return LangchainTurnMapper.to_entity(result.scalar_one())

    async def recent_turns(self, session_id: int, limit: int = 10) -> list[LangchainTurn]:
        """내림차순으로 자른 뒤 뒤집는다 — 오름차순 LIMIT이면 대화가 길어질수록
        가장 오래된 턴이 잡혀 이력이 과거에 고인다(chat 저장소에서 같은 버그를 겪었다)."""
        result = await self._session.execute(
            select(LangchainTurnOrm)
            .where(LangchainTurnOrm.session_id == session_id)
            .order_by(LangchainTurnOrm.id.desc())
            .limit(limit)
        )
        return [LangchainTurnMapper.to_entity(o) for o in reversed(result.scalars().all())]
