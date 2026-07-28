from hub.adapter.outbound.orm.langchain_session_orm import (
    LangchainSessionOrm,
    LangchainTurnOrm,
)
from hub.domain.langchain_chat.session_entity import LangchainSession, LangchainTurn


class LangchainSessionMapper:
    """LangchainSessionOrm(영속성) ↔ LangchainSession(도메인) 변환."""

    @staticmethod
    def to_entity(orm: LangchainSessionOrm) -> LangchainSession:
        return LangchainSession(
            id=orm.id, created_at=orm.created_at, user_id=orm.user_id
        )


class LangchainTurnMapper:
    """LangchainTurnOrm(영속성) ↔ LangchainTurn(도메인) 변환."""

    @staticmethod
    def to_entity(orm: LangchainTurnOrm) -> LangchainTurn:
        return LangchainTurn(
            id=orm.id,
            session_id=orm.session_id,
            role=orm.role,
            content=orm.content,
            created_at=orm.created_at,
            destination=orm.destination,
        )
