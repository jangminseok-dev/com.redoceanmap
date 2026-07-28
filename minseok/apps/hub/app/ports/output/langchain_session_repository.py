from __future__ import annotations

from abc import ABC, abstractmethod

from hub.domain.langchain_chat.session_entity import LangchainSession, LangchainTurn


class LangchainSessionRepository(ABC):
    """랭체인 대화 세션 영속성 아웃바운드 포트.

    이 슬라이스의 활동 기록 포트를 겸한다 — 턴 자체가 기록이라 로그 어댑터를 따로 두지 않는다.
    """

    @abstractmethod
    async def create_session(self, user_id: int | None = None) -> LangchainSession: ...

    @abstractmethod
    async def get_session(self, session_id: int) -> LangchainSession | None: ...

    @abstractmethod
    async def append_turn(
        self, session_id: int, role: str, content: str, destination: str | None = None
    ) -> LangchainTurn: ...

    @abstractmethod
    async def recent_turns(self, session_id: int, limit: int = 10) -> list[LangchainTurn]:
        """최근 `limit`개를 오래된 순으로 반환한다(그대로 이력 프롬프트에 실린다)."""
        ...
