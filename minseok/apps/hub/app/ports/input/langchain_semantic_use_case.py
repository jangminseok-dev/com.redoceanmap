from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.langchain_semantic_dto import (
    LangchainAskQuery,
    LangchainAskResponse,
    LangchainSemanticQuery,
    LangchainSemanticResponse,
)


class LangchainSemanticUseCase(ABC):
    """랭체인 시멘틱 게이트웨이(hub/langchain-semantic, ROM 2.0) 유스케이스.

    ROM 1.0(`SemanticUseCase`)과의 차이: 분류기는 그대로 쓰되 답변 생성을 랭체인 LCEL
    체인이 맡고, 대화가 세션 단위로 이어진다(멀티턴).
    """

    @abstractmethod
    async def introduce_myself(
        self, query: LangchainSemanticQuery
    ) -> LangchainSemanticResponse:
        """랭체인 시멘틱 게이트웨이의 자기소개 메소드."""
        ...

    @abstractmethod
    async def ask(self, query: LangchainAskQuery) -> LangchainAskResponse:
        """질문 의도를 분류하고, 세션 이력과 함께 랭체인 체인으로 답변을 생성한다."""
        ...
