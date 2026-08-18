from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.adapter.outbound.mappers.conversation_mapper import ConversationMapper, MessageMapper
from chat.adapter.outbound.orm.conversation_orm import ConversationOrm, MessageOrm
from chat.app.ports.output.conversation_repository import ConversationRepository
from chat.domain.entities.conversation_entity import (
    Conversation,
    ConversationSummary,
    Message,
    summarize_payload,
)


class ConversationPgRepository(ConversationRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(self, user_id: int | None = None) -> Conversation:
        orm = ConversationOrm(user_id=user_id)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return ConversationMapper.to_entity(orm)

    async def add_message(
        self, conversation_id: int, role: str, content: str, payload: dict | None = None,
    ) -> Message:
        result = await self._session.execute(
            insert(MessageOrm)
            .values(conversation_id=conversation_id, role=role, content=content, payload=payload)
            .returning(MessageOrm)
        )
        await self._session.commit()
        return MessageMapper.to_entity(result.scalar_one())

    async def get_messages(self, conversation_id: int, limit: int = 20) -> list[Message]:
        """최근 `limit`개를 오래된 순으로 반환한다.

        내림차순으로 잘라낸 뒤 뒤집는 게 핵심이다. 오름차순 + LIMIT이면 긴 대화에서
        **가장 오래된** N개가 잡혀, 소비자의 `history[-6:]`가 최신이 아니라 과거 턴을
        주입한다(직전 상권 코드 승계도 옛 카드를 집는다). 대화가 길수록 맥락이 뒤집혔다.
        """
        result = await self._session.execute(
            select(MessageOrm)
            .where(MessageOrm.conversation_id == conversation_id)
            .order_by(MessageOrm.id.desc())
            .limit(limit)
        )
        return [MessageMapper.to_entity(o) for o in reversed(result.scalars().all())]

    async def get_conversation(self, conversation_id: int) -> Conversation | None:
        orm = (await self._session.execute(
            select(ConversationOrm).where(ConversationOrm.id == conversation_id)
        )).scalar_one_or_none()
        return ConversationMapper.to_entity(orm) if orm else None

    async def list_conversations(self, user_id: int, limit: int = 30) -> list[ConversationSummary]:
        first_user_message = (
            select(MessageOrm.content)
            .where(MessageOrm.conversation_id == ConversationOrm.id, MessageOrm.role == "user")
            .order_by(MessageOrm.id)
            .limit(1)
            .scalar_subquery()
        )
        # 마지막 카드 payload — 목록이 "어느 워크스페이스의 무엇이었나"를 보여주는 근거.
        # 카드 없는 대화(텍스트만)는 NULL이 내려와 domain/label이 None으로 열화한다.
        last_payload = (
            select(MessageOrm.payload)
            .where(
                MessageOrm.conversation_id == ConversationOrm.id,
                MessageOrm.payload.isnot(None),
            )
            .order_by(MessageOrm.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        rows = (await self._session.execute(
            select(ConversationOrm, first_user_message, last_payload)
            .where(ConversationOrm.user_id == user_id)
            .order_by(ConversationOrm.id.desc())
            .limit(limit)
        )).all()
        summaries: list[ConversationSummary] = []
        for orm, first, payload in rows:
            domain, label = summarize_payload(payload)
            summaries.append(
                ConversationSummary(
                    id=orm.id,
                    title=(first or "").strip()[:40] or "새 대화",
                    created_at=orm.created_at,
                    domain=domain,
                    label=label,
                )
            )
        return summaries
