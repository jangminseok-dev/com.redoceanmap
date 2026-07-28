from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.langchain_semantic_dto import EngineAnswer, EngineTurn


class LangchainChatEnginePort(ABC):
    """랭체인 챗봇 엔진 아웃바운드 포트 — LCEL 체인 실행.

    계약은 "턴을 주면 답을 돌려준다"까지다. 어떤 체인을 조립하는지, 어떤 프레임워크로
    조립하는지(랭체인)는 어댑터의 세부다 — app 계층은 langchain을 import하지 않는다.
    """

    @abstractmethod
    async def converse(self, turn: EngineTurn) -> EngineAnswer:
        """대화 이력과 (있으면) 근거 컨텍스트를 태워 답변을 생성한다."""
        ...
